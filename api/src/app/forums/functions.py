import re
from collections.abc import Collection

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.forums import schemas
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Forum, Post, User
from app.repositories import ForumRepository
from app.repositories.forum_repository import SITE_ROOT_FORUM_ID
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID
from app.repositories.post_repository import SNIPPET_MATCH_END, SNIPPET_MATCH_START


async def get_forum_or_404(forum_repository: ForumRepository, forum_id: int) -> Forum:
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")
    return forum


async def get_readable_forum(
    db_session: AsyncSession, principal: User | None, forum_id: int
) -> tuple[Forum, ForumPermissions]:
    """The forum and the principal's permissions on it; one that's missing or
    unreadable is the same 404."""
    forum = await get_forum_or_404(
        ForumRepository(db_session, principal=principal), forum_id
    )
    permissions = await ForumPermissions.require_read(
        db_session, principal, forum, "Forum not found"
    )
    return forum, permissions


async def filter_readable_forum_ids(
    db_session: AsyncSession, principal: User | None, forum_ids: Collection[int]
) -> set[int]:
    """Which of the given forums the principal can read; ``None`` is the guest
    role, so the result is what the public can see. Only these forums are loaded
    and checked, so callers narrow to the forums they care about first (those
    with recent activity, say) instead of checking every forum on the site.
    Permission rules stay in ``ForumPermissions``."""
    if not forum_ids:
        return set()
    candidates = list(
        await ForumRepository(db_session, principal=principal).get_multiple(
            list(forum_ids)
        )
    )
    permissions = await ForumPermissions.load(db_session, principal, candidates)
    return {
        forum.id for forum in candidates if permissions.has(forum, Verbs.FORUM_READ)
    }


def split_snippet(snippet: str) -> list[schemas.SnippetPart]:
    """Cut a search snippet into text and matched stretches at the markers
    ``PostRepository.search`` puts around matches."""
    parts = []
    for index, chunk in enumerate(
        re.split(f"[{SNIPPET_MATCH_START}{SNIPPET_MATCH_END}]", snippet)
    ):
        # Splitting on both markers alternates plain, match, plain, match...
        if chunk:
            parts.append(schemas.SnippetPart(text=chunk, match=index % 2 == 1))
    return parts


def is_game_root_forum(forum: Forum) -> bool:
    """A game's own forum, whose title follows the game and which goes away
    with it."""
    return forum.game_id is not None and forum.parent_id == GAMES_ROOT_FORUM_ID


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
) -> dict[int, Post | None]:
    children_by_parent: dict[int | None, list[Forum]] = {}
    for forum in descendants:
        children_by_parent.setdefault(forum.parent_id, []).append(forum)

    cascaded: dict[int, Post | None] = {}

    def visit(forum_id: int) -> Post | None:
        if forum_id in cascaded:
            return cascaded[forum_id]

        own_last_post = last_posts_by_forum_id.get(forum_id)
        last_post = (
            own_last_post if own_last_post and own_last_post.published_at else None
        )
        for child in children_by_parent.get(forum_id, []):
            child_last_post = visit(child.id)
            if child_last_post and (
                last_post is None
                or child_last_post.published_at > last_post.published_at
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
        datestamp=str(post.published_at),
        author=schemas.AuthorData(id=post.author.id, username=post.author.username),
    )


def prune_unreadable(
    descendants: list[Forum], root_id: int, readable_ids: Collection[int]
) -> list[Forum]:
    """Drop forums the principal can't read, unless they lead to one they can.

    Pruned bottom-up, so an unreadable forum (e.g. the games category) stays as
    a heading over readable children, and disappears once it has none.
    """
    children_by_parent: dict[int | None, list[Forum]] = {}
    for forum in descendants:
        children_by_parent.setdefault(forum.parent_id, []).append(forum)

    kept: list[Forum] = []

    def visit(forum: Forum) -> bool:
        has_visible_child = False
        for child in children_by_parent.get(forum.id, []):
            has_visible_child = visit(child) or has_visible_child
        visible = forum.id in readable_ids or has_visible_child
        if visible:
            kept.append(forum)
        return visible

    for forum in children_by_parent.get(root_id, []):
        visit(forum)
    return kept


def build_moderated_tree(
    forums: list[Forum], moderated_ids: Collection[int]
) -> list[schemas.ModeratedForumData]:
    """Nest the forums in ``moderated_ids`` under their ancestors.

    Ancestors the principal doesn't moderate stay as headings; ``forums`` must
    include them. The site root is never listed (everything falls under it), so
    the tree starts at the top-level forums.
    """
    visible_ids = set(moderated_ids)
    for forum in forums:
        if forum.id in moderated_ids:
            visible_ids.update(forum.heritage)
    visible_ids.discard(SITE_ROOT_FORUM_ID)

    children_by_parent: dict[int | None, list[Forum]] = {}
    for forum in sorted(forums, key=lambda forum: forum.order):
        if forum.id not in visible_ids:
            continue
        parent_id = forum.parent_id if forum.parent_id in visible_ids else None
        children_by_parent.setdefault(parent_id, []).append(forum)

    def build(parent_id: int | None) -> list[schemas.ModeratedForumData]:
        return [
            schemas.ModeratedForumData(
                id=forum.id,
                title=forum.title,
                moderate=forum.id in moderated_ids,
                children=build(forum.id),
            )
            for forum in children_by_parent.get(parent_id, [])
        ]

    return build(None)


def build_forum_tree(
    descendants: list[Forum],
    root_id: int,
    last_posts_by_forum_id: dict[int, Post],
    readable_ids: Collection[int] | None = None,
    unread_ids: Collection[int] = (),
) -> list[schemas.ChildForumData]:
    """Nest ``descendants`` under ``root_id``.

    Forums outside ``readable_ids`` (when given) report no threads; pass only
    readable forums' posts in ``last_posts_by_forum_id`` to keep their last
    posts hidden too. Forums in ``unread_ids`` are flagged ``has_unread``.
    """
    children_by_parent: dict[int | None, list[Forum]] = {}
    for forum in descendants:
        children_by_parent.setdefault(forum.parent_id, []).append(forum)

    cascaded_last_posts = cascade_last_posts(descendants, last_posts_by_forum_id)

    # A forum reports its own counts (if readable) plus those of everything
    # readable below it.
    totals: dict[int, tuple[int, int]] = {}

    def total_counts(forum: Forum) -> tuple[int, int]:
        if forum.id in totals:
            return totals[forum.id]
        threads, posts = 0, 0
        if readable_ids is None or forum.id in readable_ids:
            threads, posts = forum.thread_count, forum.post_count
        for child in children_by_parent.get(forum.id, []):
            child_threads, child_posts = total_counts(child)
            threads += child_threads
            posts += child_posts
        totals[forum.id] = (threads, posts)
        return threads, posts

    def build(parent_id: int) -> list[schemas.ChildForumData]:
        return [
            schemas.ChildForumData(
                id=forum.id,
                title=forum.title,
                description=forum.description,
                forum_type=forum.forum_type,
                parent_id=forum.parent_id,
                order=forum.order,
                thread_count=total_counts(forum)[0],
                post_count=total_counts(forum)[1],
                has_unread=forum.id in unread_ids,
                last_post=build_last_post_details(cascaded_last_posts.get(forum.id)),
                children=build(forum.id),
            )
            for forum in children_by_parent.get(parent_id, [])
        ]

    return build(root_id)
