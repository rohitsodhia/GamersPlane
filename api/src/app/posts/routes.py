from fastapi import APIRouter

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.helpers.decorators import public
from app.middleware import Auth
from app.posts import schemas
from app.repositories import PostRepository, ThreadRepository

posts = APIRouter(prefix="/posts")


@posts.get("", response_model=schemas.GetPostsResponse)
@public
async def get_posts(
    db_session: DBSessionDependency, auth: Auth, thread_id: int, page: int = 1
):
    if page < 1:
        page = 1

    thread_repository = ThreadRepository(db_session, auth=auth)
    thread = await thread_repository.get(thread_id)

    if thread is None:
        raise NotFoundException("Thread not found")

    post_repository = PostRepository(db_session, auth=auth)
    posts = await post_repository.get_all(thread_id, page=page)

    posts_data = []
    for post in posts:
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


# @posts.post("", response_model=schemas.NewThreadResponse)
# async def create_thread(
#     db_session: DBSessionDependency,
#     auth: Auth,
#     principal: Principal,
#     thread_data: schemas.NewThreadInput,
# ):
#     forum_repository = ForumRepository(db_session, auth=auth)
#     forum = await forum_repository.get(thread_data.forum_id)
#     if forum is None:
#         raise NotFoundException("Forum not found")

#     thread_repository = ThreadRepository(db_session, auth=auth)
#     thread = await thread_repository.create(
#         thread_data.forum_id,
#         thread_data.options,
#     )

#     post_repository = PostRepository(db_session, auth=auth)
#     post = await post_repository.create(
#         thread.id, principal.id, thread_data.title, thread_data.body
#     )
#     await thread_repository.attach_new_post(thread, post)

#     return schemas.NewThreadResponse(id=thread.id)
