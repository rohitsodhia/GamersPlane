from app.exceptions import NotFoundException
from app.forums import schemas
from app.models import Forum, Post
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


def cascade_last_posts(
    descendants: list[Forum], last_posts_by_forum_id: dict[int, Post]
) -> dict[int, Post]:
    children_by_parent: dict[int | None, list[Forum]] = {}
    for forum in descendants:
        children_by_parent.setdefault(forum.parent_id, []).append(forum)

    cascaded: dict[int, Post] = {}

    def visit(forum_id: int) -> Post | None:
        if forum_id in cascaded:
            return cascaded[forum_id]

        last_post = last_posts_by_forum_id.get(forum_id)
        for child in children_by_parent.get(forum_id, []):
            child_last_post = visit(child.id)
            if child_last_post and (
                last_post is None or child_last_post.created_at > last_post.created_at
            ):
                last_post = child_last_post
        cascaded[forum_id] = last_post
        return last_post

    for forum in descendants:
        visit(forum.id)

    return cascaded


def build_last_post_details(post: Post | None) -> schemas.LastPostDetails | None:
    if post is None:
        return None

    return schemas.LastPostDetails(
        id=post.id,
        title=post.title,
        datestamp=str(post.created_at),
        author=schemas.AuthorData(id=post.author.id, username=post.author.username),
    )


def build_forum_tree(
    descendants: list[Forum],
    root_id: int,
    last_posts_by_forum_id: dict[int, Post],
) -> list[schemas.ChildForumData]:
    children_by_parent: dict[int | None, list[Forum]] = {}
    for forum in descendants:
        children_by_parent.setdefault(forum.parent_id, []).append(forum)

    cascaded_last_posts = cascade_last_posts(descendants, last_posts_by_forum_id)

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
                last_post=build_last_post_details(cascaded_last_posts.get(forum.id)),
                children=build(forum.id),
            )
            for forum in children_by_parent.get(parent_id, [])
        ]

    return build(root_id)
