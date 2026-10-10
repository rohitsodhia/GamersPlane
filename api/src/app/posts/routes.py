from fastapi import APIRouter, BackgroundTasks, status

from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException, ValidationError
from app.forums.permissions import ForumPermissions, Verbs
from app.helpers.decorators import public
from app.middleware import Principal
from app.models import Post
from app.posts import schemas
from app.posts.attachments import plan_attachments, save_attachments
from app.posts.functions import check_post_change, validate_roll_visibility
from app.posts.visibility import redact_draw, redact_roll
from app.repositories import (
    PollRepository,
    PostRepository,
    ReadTrackingRepository,
    ThreadRepository,
)
from app.threads.discord import queue_post_webhook
from app.threads.functions import merge_thread_options
from app.threads.poll_functions import (
    build_poll_data,
    check_poll_input,
    require_add_poll,
)

posts = APIRouter(prefix="/posts")


@posts.get("", response_model=schemas.GetPostsResponse)
@public
async def get_posts(
    db_session: DBSessionDependency, principal: Principal, thread_id: int, page: int = 1
):
    if page < 1:
        page = 1

    thread_repository = ThreadRepository(db_session, principal=principal)
    thread = await thread_repository.get(thread_id)
    if thread is None:
        raise NotFoundException("Thread not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )

    post_repository = PostRepository(db_session, principal=principal)
    posts = list(await post_repository.get_all(thread_id, page=page))

    # Moderator status is per request (it's per forum), not per roll.
    is_moderator = permissions.has(thread.forum, Verbs.FORUM_MODERATE)
    rolls = await post_repository.get_rolls([post.id for post in posts])
    draws = await post_repository.get_draws([post.id for post in posts])

    posts_data = []
    for post in posts:
        assert post.published_at
        is_author = principal is not None and post.author_id == principal.id
        posts_data.append(
            schemas.PostData(
                id=post.id,
                title=post.title,
                datestamp=post.published_at,
                author=schemas.AuthorData(
                    id=post.author.id,
                    username=post.author.username,
                    avatar=post.author.avatar_url,
                ),
                body=post.body,
                rolls=[
                    redact_roll(roll, full_view=is_author or is_moderator)
                    for roll in rolls[post.id]
                ],
                draws=[
                    redact_draw(draw, is_author=is_author) for draw in draws[post.id]
                ],
            )
        )

    return schemas.GetPostsResponse(
        posts=posts_data,
        count=await post_repository.count_by_thread(thread_id),
        page=page,
    )


@posts.get("/{post_id}", response_model=schemas.GetPostResponse)
async def get_post(db_session: DBSessionDependency, principal: Principal, post_id: int):
    post_repository = PostRepository(db_session, principal=principal)
    post = await post_repository.get(post_id)
    if post is None:
        raise NotFoundException("Post not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, post.thread.forum, "Post not found"
    )
    full_view = principal.id == post.author_id or permissions.has(
        post.thread.forum, Verbs.FORUM_MODERATE
    )
    rolls = (await post_repository.get_rolls([post.id]))[post.id]
    draws = (await post_repository.get_draws([post.id]))[post.id]
    is_first_post = post.thread.first_post_id == post.id
    # The edit form needs the counts (to warn before dropping voted options), so
    # the poll goes to whoever may edit the first post, whatever they'd see on the
    # thread page.
    poll = None
    if is_first_post:
        try:
            check_post_change(permissions, post, principal, Verbs.FORUM_EDIT)
        except ForbiddenException:
            pass
        else:
            poll = await build_poll_data(
                PollRepository(db_session, principal=principal),
                post.thread,
                permissions,
                principal,
                force_results=True,
            )

    return schemas.GetPostResponse(
        id=post.id,
        title=post.title,
        datestamp=post.published_at,
        author=schemas.AuthorData(
            id=post.author.id,
            username=post.author.username,
            avatar=post.author.avatar_url,
        ),
        body=post.body,
        rolls=[redact_roll(roll, full_view=full_view) for roll in rolls],
        draws=[
            redact_draw(draw, is_author=principal.id == post.author_id)
            for draw in draws
        ],
        is_first_post=is_first_post,
        discord_webhook=post.thread.options.discord_webhook
        if is_first_post and principal.id == post.author_id
        else None,
        poll=poll,
        thread_id=post.thread_id,
        forum_id=post.thread.forum_id,
        page=await post_repository.get_page_number(post),
    )


@posts.post("", response_model=schemas.NewPostResponse)
async def create_post(
    background_tasks: BackgroundTasks,
    db_session: DBSessionDependency,
    principal: Principal,
    post_data: schemas.NewPostInput,
):
    thread_repository = ThreadRepository(db_session, principal=principal)
    thread = await thread_repository.get(post_data.thread_id)
    if thread is None:
        raise NotFoundException("Thread not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )
    if not permissions.has(thread.forum, Verbs.FORUM_MODERATE):
        if thread.options.locked:
            raise ForbiddenException("Thread is locked")
        if not permissions.has(thread.forum, Verbs.FORUM_WRITE):
            raise ForbiddenException("You can't post in this forum")

    attachments = await plan_attachments(
        db_session,
        principal,
        thread.forum,
        permissions,
        thread.options,
        post_data.rolls,
        post_data.draws,
    )

    post_repository = PostRepository(db_session, principal=principal)
    post = await post_repository.create(
        thread.id,
        principal.id,
        post_data.title,
        post_data.body,
        state=Post.States.PUBLISHED,
    )
    await save_attachments(db_session, principal, post, attachments)
    await thread_repository.attach_new_post(thread, post)
    assert post.published_at is not None
    await ReadTrackingRepository(db_session, principal=principal).mark_viewed(
        thread, post.published_at
    )
    await queue_post_webhook(
        background_tasks,
        post_repository,
        thread.options.discord_webhook,
        post,
        principal,
    )

    return schemas.NewPostResponse(id=post.id)


@posts.patch("/{post_id}", response_model=schemas.EditPostResponse)
async def edit_post(
    background_tasks: BackgroundTasks,
    db_session: DBSessionDependency,
    principal: Principal,
    post_id: int,
    post_data: schemas.EditPostInput,
):
    post_repository = PostRepository(db_session, principal=principal)
    post = await post_repository.get(post_id)
    if post is None:
        raise NotFoundException("Post not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, post.thread.forum, "Post not found"
    )
    check_post_change(permissions, post, principal, Verbs.FORUM_EDIT)

    # Moderators can change a roll's visibility but not add to someone else's
    # post: a draw's cards are shown to the post's author, not to whoever drew.
    if (post_data.rolls or post_data.draws) and post.author_id != principal.id:
        raise ForbiddenException("Only the author can add rolls or draws to a post")
    existing_rolls = (await post_repository.get_rolls([post.id]))[post.id]
    visibility_changes = validate_roll_visibility(
        existing_rolls, post_data.roll_visibility
    )
    # Merged first so the same request can enable rolls/draws and use them.
    options = post.thread.options
    if post_data.thread_options is not None:
        if post.thread.first_post_id != post.id:
            raise ValidationError(
                "Thread options can only be changed on the first post"
            )
        options = merge_thread_options(
            permissions, post.thread.forum, options, post_data.thread_options
        )
    # Absent leaves the poll alone; null removes it; an object sets it.
    poll_sent = "poll" in post_data.model_fields_set
    poll_repository = PollRepository(db_session, principal=principal)
    poll = None
    poll_options = []
    if poll_sent:
        if post.thread.first_post_id != post.id:
            raise ValidationError("A poll can only be changed on the first post")
        require_add_poll(permissions, post.thread.forum)
        poll = await poll_repository.get(post.thread_id)
        if post_data.poll is not None:
            poll_options = await check_poll_input(poll_repository, poll, post_data.poll)
    attachments = await plan_attachments(
        db_session,
        principal,
        post.thread.forum,
        permissions,
        options,
        post_data.rolls,
        post_data.draws,
    )

    if poll_sent:
        if post_data.poll is None:
            if poll is not None:
                await poll_repository.delete(poll)
        elif poll is None:
            await poll_repository.create(post.thread_id, post_data.poll)
        else:
            await poll_repository.apply_edit(poll, poll_options, post_data.poll)
    if options is not post.thread.options:
        await ThreadRepository(db_session, principal=principal).update_options(
            post.thread, options
        )
    await post_repository.update(post, post_data.title, post_data.body)
    for roll, change in visibility_changes:
        await post_repository.set_roll_visibility(
            roll, change.hide_reason, change.hide_dice, change.hide_result
        )
    await save_attachments(db_session, principal, post, attachments)
    if not post_data.minor_edit:
        await queue_post_webhook(
            background_tasks,
            post_repository,
            options.discord_webhook,
            post,
            post.author,
            edited=True,
        )

    return schemas.EditPostResponse(id=post.id)


@posts.post(
    "/{post_id}/draws/{draw_id}/cards/{index}/toggle",
    response_model=schemas.PostDrawData,
)
async def toggle_draw_card(
    db_session: DBSessionDependency,
    principal: Principal,
    post_id: int,
    draw_id: int,
    index: int,
):
    """Flip whether a drawn card is shown to other viewers.

    Only the post's author may do this. Moderators and GMs can't, as revealing a
    card to them would be revealing its face. In a locked thread the author also
    needs to moderate the forum, as with any other change to a post.
    """
    post_repository = PostRepository(db_session, principal=principal)
    post = await post_repository.get(post_id)
    if post is None:
        raise NotFoundException("Post not found")
    forum = post.thread.forum
    permissions = await ForumPermissions.require_read(
        db_session, principal, forum, "Post not found"
    )
    if post.author_id != principal.id:
        raise ForbiddenException("Only the author can reveal or hide cards")
    if post.thread.options.locked and not permissions.has(forum, Verbs.FORUM_MODERATE):
        raise ForbiddenException("Thread is locked")

    draw = await post_repository.get_draw(draw_id)
    if draw is None or draw.post_id != post.id:
        raise NotFoundException("Draw not found")
    if not 0 <= index < len(draw.cards):
        raise ValidationError("Card index out of range")

    draw = await post_repository.set_card_revealed(
        draw, index, not draw.revealed[index]
    )
    return redact_draw(draw, is_author=True)


@posts.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    db_session: DBSessionDependency,
    principal: Principal,
    post_id: int,
):
    post_repository = PostRepository(db_session, principal=principal)
    post = await post_repository.get(post_id)
    if post is None:
        raise NotFoundException("Post not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, post.thread.forum, "Post not found"
    )
    # Deleting the first post deletes the whole thread.
    check_post_change(
        permissions,
        post,
        principal,
        Verbs.FORUM_DELETE_THREAD
        if post.id == post.thread.first_post_id
        else Verbs.FORUM_DELETE,
    )

    thread_repository = ThreadRepository(db_session, principal=principal)
    thread = post.thread
    await post_repository.delete(post)
    if post.id == thread.first_post_id:
        await thread_repository.delete(thread)
    else:
        await thread_repository.detach_post(thread, post)
