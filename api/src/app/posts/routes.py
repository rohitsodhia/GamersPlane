from fastapi import APIRouter, status

from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.forums.permissions import ForumPermissions, Verbs
from app.helpers.decorators import public
from app.middleware import Principal
from app.models import Post
from app.posts import schemas
from app.posts.functions import check_post_change
from app.repositories import PostRepository, ReadTrackingRepository, ThreadRepository

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
    await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )

    post_repository = PostRepository(db_session, principal=principal)
    posts = await post_repository.get_all(thread_id, page=page)

    posts_data = []
    for post in posts:
        assert post.published_at
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
    await ForumPermissions.require_read(
        db_session, principal, post.thread.forum, "Post not found"
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
        is_first_post=post.thread.first_post_id == post.id,
        thread_id=post.thread_id,
        forum_id=post.thread.forum_id,
        page=await post_repository.get_page_number(post),
    )


@posts.post("", response_model=schemas.NewPostResponse)
async def create_post(
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

    post_repository = PostRepository(db_session, principal=principal)
    post = await post_repository.create(
        thread.id,
        principal.id,
        post_data.title,
        post_data.body,
        state=Post.States.PUBLISHED,
    )
    await thread_repository.attach_new_post(thread, post)
    assert post.published_at is not None
    await ReadTrackingRepository(db_session, principal=principal).mark_viewed(
        thread, post.published_at
    )

    return schemas.NewPostResponse(id=post.id)


@posts.patch("/{post_id}", response_model=schemas.EditPostResponse)
async def edit_post(
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

    await post_repository.update(post, post_data.title, post_data.body)

    return schemas.EditPostResponse(id=post.id)


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
