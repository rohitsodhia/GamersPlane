from fastapi import APIRouter, BackgroundTasks, status

from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException, ValidationError
from app.forums.permissions import ForumPermissions, Verbs
from app.helpers.decorators import public
from app.middleware import Principal
from app.models import Post, Thread, User
from app.posts.attachments import plan_attachments, save_attachments
from app.posts.functions import check_post_change, validate_posted_as
from app.repositories import (
    ForumRepository,
    PollRepository,
    PostRepository,
    ReadTrackingRepository,
    ThreadRepository,
)
from app.threads import schemas
from app.threads.discord import queue_post_webhook
from app.threads.functions import (
    build_post_data,
    check_thread_options,
    merge_thread_options,
)
from app.threads.poll_functions import (
    build_poll_data,
    check_poll_input,
    require_add_poll,
)
from app.threads.poll_schemas import PollData, VoteInput

threads = APIRouter(prefix="/threads")


@threads.get("", response_model=schemas.GetThreadsResponse)
@public
async def get_threads(
    db_session: DBSessionDependency, principal: Principal, forum_id: int, page: int = 1
):
    if page < 1:
        page = 1

    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")
    await ForumPermissions.require_read(db_session, principal, forum, "Forum not found")

    thread_repository = ThreadRepository(db_session, principal=principal)
    threads = list(await thread_repository.get_all(forum_id, page=page) or [])

    unread_ids = (
        await ReadTrackingRepository(db_session, principal=principal).unread_thread_ids(
            threads
        )
        if principal
        else set()
    )

    threads_data = []
    for thread in threads:
        assert thread.first_post is not None
        assert thread.last_post is not None
        threads_data.append(
            schemas.ThreadData(
                id=thread.id,
                first_post=build_post_data(thread.first_post),
                last_post=build_post_data(thread.last_post),
                options=schemas.ThreadOptionsData.model_validate(thread.options),
                post_count=thread.post_count,
                has_unread=thread.id in unread_ids,
            )
        )

    return schemas.GetThreadsResponse(
        threads=threads_data,
        count=await thread_repository.count_by_forum(forum_id),
        page=page,
    )


@threads.get("/{thread_id}", response_model=schemas.GetThreadResponse)
@public
async def get_thread(
    db_session: DBSessionDependency, principal: Principal, thread_id: int
):
    thread_repository = ThreadRepository(db_session, principal=principal)
    thread = await thread_repository.get(thread_id)
    if thread is None:
        raise NotFoundException("Thread not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )
    assert thread.first_post is not None

    first_unread_post = None
    first_unread_page = None
    if principal:
        post_repository = PostRepository(db_session, principal=principal)
        read_point = await ReadTrackingRepository(
            db_session, principal=principal
        ).thread_read_point(thread)
        first_unread_post = await post_repository.get_first_published_after(
            thread.id, read_point
        )
        if first_unread_post:
            first_unread_page = await post_repository.get_page_number(first_unread_post)

    poll = await build_poll_data(
        PollRepository(db_session, principal=principal), thread, permissions, principal
    )

    return schemas.GetThreadResponse(
        id=thread.id,
        forum_id=thread.forum_id,
        title=thread.first_post.title,
        options=schemas.ThreadOptionsData.model_validate(thread.options),
        first_post_id=thread.first_post.id,
        first_unread_post_id=first_unread_post.id if first_unread_post else None,
        first_unread_page=first_unread_page,
        permissions=sorted(verb.value for verb in permissions.allowed(thread.forum)),
        poll=poll,
    )


@threads.post("", response_model=schemas.NewThreadResponse)
async def create_thread(
    background_tasks: BackgroundTasks,
    db_session: DBSessionDependency,
    principal: Principal,
    thread_data: schemas.NewThreadInput,
):
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await forum_repository.get(thread_data.forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, forum, "Forum not found"
    )
    if not permissions.has(forum, Verbs.FORUM_CREATE_THREAD):
        raise ForbiddenException("You can't create threads in this forum")
    check_thread_options(permissions, forum, thread_data.options)
    if thread_data.poll is not None:
        require_add_poll(permissions, forum)
        await check_poll_input(
            PollRepository(db_session, principal=principal), None, thread_data.poll
        )
    if thread_data.posted_as_id is not None:
        await validate_posted_as(db_session, principal, forum, thread_data.posted_as_id)
    attachments = await plan_attachments(
        db_session,
        principal,
        forum,
        permissions,
        thread_data.options,
        thread_data.rolls,
        thread_data.draws,
    )

    thread_repository = ThreadRepository(db_session, principal=principal)
    thread = await thread_repository.create(
        thread_data.forum_id,
        thread_data.options,
    )

    post_repository = PostRepository(db_session, principal=principal)
    post = await post_repository.create(
        thread.id,
        principal.id,
        thread_data.title,
        thread_data.body,
        state=Post.States.PUBLISHED,
        posted_as_id=thread_data.posted_as_id,
    )
    await save_attachments(db_session, principal, post, attachments)
    await thread_repository.attach_new_post(thread, post)
    if thread_data.poll is not None:
        await PollRepository(db_session, principal=principal).create(
            thread.id, thread_data.poll
        )
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

    return schemas.NewThreadResponse(id=thread.id)


@threads.patch("/{thread_id}", response_model=schemas.ThreadOptionsData)
async def update_thread(
    db_session: DBSessionDependency,
    principal: Principal,
    thread_id: int,
    data: schemas.UpdateThreadInput,
):
    """Change a thread's options. Only the thread's author (while it is unlocked)
    or a moderator may, and each option needs its own verb."""
    thread_repository = ThreadRepository(db_session, principal=principal)
    thread = await thread_repository.get(thread_id)
    if thread is None:
        raise NotFoundException("Thread not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )
    assert thread.first_post is not None
    check_post_change(permissions, thread.first_post, principal, Verbs.FORUM_EDIT)

    options = merge_thread_options(
        permissions, thread.forum, thread.options, data.options
    )
    await thread_repository.update_options(thread, options)
    return schemas.ThreadOptionsData.model_validate(options)


async def get_readable_thread(
    db_session: DBSessionDependency, principal: User, thread_id: int
) -> Thread:
    thread = await ThreadRepository(db_session, principal=principal).get(thread_id)
    if thread is None:
        raise NotFoundException("Thread not found")
    await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )
    return thread


@threads.post("/{thread_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_thread_viewed(
    db_session: DBSessionDependency,
    principal: Principal,
    thread_id: int,
    data: schemas.MarkThreadViewedInput,
):
    """Record that the principal has seen the thread up to the given post."""
    thread = await get_readable_thread(db_session, principal, thread_id)
    post = await PostRepository(db_session, principal=principal).get(data.post_id)
    if (
        post is None
        or post.thread_id != thread.id
        or post.state != Post.States.PUBLISHED
        or post.published_at is None
    ):
        raise NotFoundException("Post not found")

    await ReadTrackingRepository(db_session, principal=principal).mark_viewed(
        thread, post.published_at
    )


@threads.post("/{thread_id}/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_thread_read(
    db_session: DBSessionDependency, principal: Principal, thread_id: int
):
    thread = await get_readable_thread(db_session, principal, thread_id)
    await ReadTrackingRepository(db_session, principal=principal).mark_thread_read(
        thread
    )


@threads.post("/{thread_id}/mark-unread", status_code=status.HTTP_204_NO_CONTENT)
async def mark_thread_unread(
    db_session: DBSessionDependency, principal: Principal, thread_id: int
):
    thread = await get_readable_thread(db_session, principal, thread_id)
    await ReadTrackingRepository(db_session, principal=principal).mark_thread_unread(
        thread
    )


@threads.put("/{thread_id}/poll/vote", response_model=PollData)
async def vote_in_poll(
    db_session: DBSessionDependency,
    principal: Principal,
    thread_id: int,
    data: VoteInput,
):
    """Set the principal's votes in the thread's poll, replacing any they had.

    Nobody votes in a locked thread, moderators included.
    """
    thread = await ThreadRepository(db_session, principal=principal).get(thread_id)
    if thread is None:
        raise NotFoundException("Thread not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )
    poll_repository = PollRepository(db_session, principal=principal)
    poll = await poll_repository.get(thread.id)
    if poll is None:
        raise NotFoundException("Poll not found")

    if thread.options.locked:
        raise ForbiddenException("Thread is locked")
    if not permissions.has(thread.forum, Verbs.FORUM_WRITE):
        raise ForbiddenException("You can't vote in this forum")
    previous_votes = await poll_repository.user_votes(thread.id, principal.id)
    if previous_votes and not poll.allow_revoting:
        raise ForbiddenException("You have already voted in this poll")

    option_ids = data.option_ids
    if not option_ids:
        raise ValidationError("Choose at least one option")
    if len(option_ids) > poll.options_per_user:
        raise ValidationError(f"You can choose at most {poll.options_per_user} options")
    if len(set(option_ids)) != len(option_ids):
        raise ValidationError("An option can only be chosen once")
    valid_ids = {option.id for option in await poll_repository.get_options(thread.id)}
    if not set(option_ids) <= valid_ids:
        raise ValidationError("An option isn't part of this poll")

    await poll_repository.replace_votes(thread.id, principal.id, option_ids)
    poll_data = await build_poll_data(poll_repository, thread, permissions, principal)
    assert poll_data is not None
    return poll_data
