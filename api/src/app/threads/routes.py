from fastapi import APIRouter

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.helpers.decorators import public
from app.middleware import Auth, Principal
from app.repositories import ForumRepository, PostRepository, ThreadRepository
from app.threads import schemas
from app.threads.functions import build_post_data

threads = APIRouter(prefix="/threads")


@threads.get("", response_model=schemas.GetThreadsResponse)
@public
async def get_threads(
    db_session: DBSessionDependency, auth: Auth, forum_id: int, page: int = 1
):
    if page < 1:
        page = 1

    forum_repository = ForumRepository(db_session, auth=auth)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")

    thread_repository = ThreadRepository(db_session, auth=auth)
    threads = await thread_repository.get_all(forum_id, page=page) or []

    threads_data = []
    for thread in threads:
        assert thread.first_post is not None
        assert thread.last_post is not None
        threads_data.append(
            schemas.ThreadData(
                id=thread.id,
                title=thread.first_post.title,
                first_post=build_post_data(thread.first_post),
                last_post=build_post_data(thread.last_post),
                options=thread.options,
                post_count=thread.post_count,
            )
        )

    return schemas.GetThreadsResponse(
        threads=threads_data,
        count=await thread_repository.count_by_forum(forum_id),
        page=page,
    )


@threads.post("", response_model=schemas.NewThreadResponse)
async def create_thread(
    db_session: DBSessionDependency,
    auth: Auth,
    principal: Principal,
    thread_data: schemas.NewThreadInput,
):
    forum_repository = ForumRepository(db_session, auth=auth)
    forum = await forum_repository.get(thread_data.forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")

    thread_repository = ThreadRepository(db_session, auth=auth)
    thread = await thread_repository.create(
        thread_data.forum_id,
        thread_data.options,
    )

    post_repository = PostRepository(db_session, auth=auth)
    post = await post_repository.create(
        thread.id, principal.id, thread_data.title, thread_data.body
    )
    await thread_repository.attach_new_post(thread, post)

    return schemas.NewThreadResponse(id=thread.id)
