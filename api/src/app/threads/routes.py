from fastapi import APIRouter

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.helpers.decorators import public
from app.middleware import Auth
from app.repositories import ForumRepository, ThreadRepository
from app.threads import schemas
from app.threads.functions import build_post_data

threads = APIRouter(prefix="/threads")


@threads.get("", response_model=schemas.GetThreads)
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

    return schemas.GetThreads(
        threads=threads_data,
        count=await thread_repository.count_by_forum(forum_id),
        page=page,
    )
