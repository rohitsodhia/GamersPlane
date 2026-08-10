from app.exceptions import NotFoundException
from app.forums import schemas
from app.models import Forum
from app.repositories import ForumRepository


async def get_heritage(
    forum_repository: ForumRepository, heritage: list[int]
) -> list[Forum]:
    heritage_forums = await forum_repository.get_multiple(heritage)
    forums_by_id = {forum.id: forum for forum in heritage_forums}

    ordered_heritage = []
    for forum_id in heritage:
        if forum_id not in forums_by_id:
            raise NotFoundException(f'Heritage forum "{forum_id}" is missing')
        ordered_heritage.append(forums_by_id[forum_id])

    return ordered_heritage


def build_forum_tree(
    descendants: list[Forum], root_id: int
) -> list[schemas.ChildForumData]:
    children_by_parent: dict[int | None, list[Forum]] = {}
    for forum in descendants:
        children_by_parent.setdefault(forum.parent_id, []).append(forum)

    def build(parent_id: int) -> list[schemas.ChildForumData]:
        return [
            schemas.ChildForumData(
                id=forum.id,
                title=forum.title,
                description=forum.description,
                forum_type=forum.forum_type,
                parent_id=forum.parent_id,
                order=forum.order,
                thread_count=forum.thread_count,
                post_count=0,
                children=build(forum.id),
            )
            for forum in children_by_parent.get(parent_id, [])
        ]

    return build(root_id)
