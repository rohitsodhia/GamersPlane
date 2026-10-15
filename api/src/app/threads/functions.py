from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenException, NotFoundException
from app.forums.functions import filter_readable_forum_ids
from app.forums.permissions import ForumPermissions, Verbs
from app.middleware import Principal
from app.models import Forum, Post, Thread
from app.repositories import (
    ForumRepository,
    GameRepository,
    ReadTrackingRepository,
    ThreadRepository,
)
from app.repositories.forum_repository import SITE_ROOT_FORUM_ID
from app.threads import schemas
from app.threads.option_schemas import ThreadOptionsUpdate
from app.threads.schemas import ThreadListScope

# How far back the cross-forum thread listings look, by last post.
RECENT_THREADS_WINDOW = timedelta(weeks=1)

# The forum verb needed to change each thread option. The options themselves
# act as thread-wide switches for everyone posting in the thread.
OPTION_VERBS = {
    "sticky": Verbs.FORUM_MODERATE,
    "locked": Verbs.FORUM_MODERATE,
    "allow_public_posting": Verbs.FORUM_MODERATE,
    "discord_webhook": Verbs.FORUM_MODERATE,
    "allow_rolls": Verbs.FORUM_ADD_ROLLS,
    "allow_draws": Verbs.FORUM_ADD_DRAWS,
}


async def list_recent_threads(
    db_session: AsyncSession,
    principal: Principal | None,
    scope: ThreadListScope,
    page: int,
) -> schemas.GetThreadListingResponse:
    """A page of the threads active in the past ``RECENT_THREADS_WINDOW`` that
    fit the scope, newest last post first. ``Principal`` is None for a guest, who
    gets 403 for the unread scope as on any route that needs a login."""
    if scope is ThreadListScope.UNREAD and principal is None:
        raise ForbiddenException()

    since = datetime.now(UTC) - RECENT_THREADS_WINDOW
    thread_repository = ThreadRepository(db_session, principal=principal)
    # Start from the forums with recent activity, so the permission check covers
    # only those rather than every forum on the site.
    active_ids = await thread_repository.recently_active_forum_ids(
        since,
        game_only=scope in (ThreadListScope.LATEST_GAME, ThreadListScope.LATEST_PUBLIC),
    )
    # Public games are the game forums the guest role (not the principal) can read.
    # Every other scope shows game forums only for the principal's own games (the
    # same rule as the forum index); a guest has none.
    own_game_ids = None
    if scope is not ThreadListScope.LATEST_PUBLIC:
        own_game_ids = (
            await GameRepository(
                db_session, principal=principal
            ).get_forum_listed_game_ids(principal.id)
            if principal
            else set()
        )
    readable_ids = await filter_readable_forum_ids(
        db_session,
        None if scope is ThreadListScope.LATEST_PUBLIC else principal,
        active_ids,
        only_game_ids=own_game_ids,
    )
    forum_repository = ForumRepository(db_session, principal=principal)

    found, count = await thread_repository.get_recent(
        readable_ids,
        since,
        page=page,
        unread_only=scope is ThreadListScope.UNREAD,
    )

    unread_ids = (
        await ReadTrackingRepository(db_session, principal=principal).unread_thread_ids(
            found
        )
        if principal
        else set()
    )
    heritage_ids = {
        forum_id for thread in found for forum_id in thread.forum.heritage
    } - {SITE_ROOT_FORUM_ID}
    heritage_titles = {
        forum.id: forum.title
        for forum in (
            await forum_repository.get_multiple(list(heritage_ids))
            if heritage_ids
            else []
        )
    }

    threads = []
    for thread in found:
        assert thread.first_post is not None
        assert thread.last_post is not None
        forum = thread.forum
        threads.append(
            schemas.ThreadListingData(
                id=thread.id,
                first_post=build_post_data(thread.first_post),
                last_post=build_post_data(thread.last_post),
                options=schemas.ThreadOptionsData.model_validate(thread.options),
                post_count=thread.post_count,
                has_unread=thread.id in unread_ids,
                forum=schemas.ThreadListingForum(
                    id=forum.id,
                    title=forum.title,
                    game_id=forum.game_id,
                    heritage=[
                        schemas.ListingForumRef(
                            id=forum_id, title=heritage_titles[forum_id]
                        )
                        for forum_id in forum.heritage
                        if forum_id in heritage_titles
                    ],
                ),
            )
        )
    return schemas.GetThreadListingResponse(threads=threads, count=count, page=page)


async def get_readable_thread(
    db_session: AsyncSession, principal: Principal, thread_id: int
) -> tuple[Thread, ForumPermissions]:
    """The thread and the principal's permissions on its forum; a thread that's
    missing or in a forum they can't read is the same 404."""
    thread = await ThreadRepository(db_session, principal=principal).get(thread_id)
    if thread is None:
        raise NotFoundException("Thread not found")
    permissions = await ForumPermissions.require_read(
        db_session, principal, thread.forum, "Thread not found"
    )
    return thread, permissions


def build_post_data(post: Post) -> schemas.PostData:
    return schemas.PostData(
        id=post.id,
        title=post.title,
        datestamp=str(post.published_at),
        author=schemas.AuthorData(id=post.author.id, username=post.author.username),
    )


def merge_thread_options(
    permissions: ForumPermissions,
    forum: Forum,
    current: Thread.Options,
    update: ThreadOptionsUpdate,
) -> Thread.Options:
    """Apply a partial update to a thread's options, returning a new object.

    A field changes only if it was sent and differs from the current value, and
    changing it (on or off) needs its ``OPTION_VERBS`` verb. A boolean sent as
    ``null`` is skipped as not sent; ``discord_webhook`` ``null`` clears it.
    """
    changes = {}
    for field in update.model_fields_set:
        value = getattr(update, field)
        if value is None and field != "discord_webhook":
            continue
        if value == getattr(current, field):
            continue
        if not permissions.has(forum, OPTION_VERBS[field]):
            raise ForbiddenException(f"You can't change {field} on this thread")
        changes[field] = value
    return current.model_copy(update=changes)


def check_thread_options(
    permissions: ForumPermissions, forum: Forum, options: Thread.Options
) -> None:
    """Raise if a new thread sets an option the principal may not set.

    Every option defaults to a falsy value, so "set" means truthy; that also
    treats an empty webhook string (what the form sends) as unset.
    """
    for field, verb in OPTION_VERBS.items():
        if getattr(options, field) and not permissions.has(forum, verb):
            raise ForbiddenException(f"You can't set {field} on this thread")
