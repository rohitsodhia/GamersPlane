from sqlalchemy.ext.asyncio import AsyncSession

from app.events import schemas
from app.forums.functions import filter_readable_forum_ids
from app.forums.permissions import ForumPermissions, Verbs
from app.helpers.prose import mentioned_user_ids
from app.models import Event, Forum, Post, Thread, User
from app.repositories import EventRepository

# Most candidate mentions looked at to fill one page. Mentions in forums the user
# can no longer read are dropped after the query, so a page can need more than one
# batch; this keeps a long hidden history from turning into an unbounded scan.
MAX_MENTIONS_SCANNED = 500


async def sync_post_mentions(
    db_session: AsyncSession, post: Post, thread: Thread, forum: Forum
) -> None:
    """Bring the post's mention notifications in step with its body: notify users
    newly mentioned, and retract the notice of users no longer mentioned.

    A user is only ever notified once per post: anyone who already has a row
    (read or not) is left alone, so re-saving never re-notifies. The post's author,
    users who don't exist, are banned or suspended, or can't read the forum aren't
    notified. A retraction goes by the body alone, so a user who has since lost
    access to the forum keeps their row. The event is always the author's, whoever
    made the edit, and goes once nobody is left.
    """
    if post.state != Post.States.PUBLISHED:
        return
    mentioned = set(mentioned_user_ids(post.body))
    repo = EventRepository(db_session)
    event = await repo.get_post_event(post.id, Event.Types.MENTION)
    existing = await repo.get_recipient_ids(event.id) if event is not None else set()

    removed = existing - mentioned
    if event is not None and removed:
        await repo.remove_recipients(event.id, removed)

    candidates = mentioned - existing - {post.author_id}
    users = await repo.get_notifiable_users(candidates)
    permissions = await ForumPermissions.load_for_users(db_session, users, forum)
    added = {
        user.id for user in users if permissions[user.id].has(forum, Verbs.FORUM_READ)
    }
    if added:
        if event is None:
            event = await repo.create_event(
                Event.Types.MENTION, post.author_id, post.id, thread.id
            )
        await repo.add_recipients(event.id, added)

    if event is not None and not ((existing - removed) | added):
        await repo.delete_event(event.id)


async def build_mentions(
    db_session: AsyncSession, user: User, limit: int, before: int | None
) -> tuple[list[schemas.MentionItem], bool]:
    """A page of the user's mentions (newest first, the ones with an event id
    below ``before``) and whether there are more after it. Mentions of deleted or
    unpublished posts, or in forums the user can't read now, are left out.

    Candidates come in batches of ``limit + 1`` until that many readable ones are
    found, up to ``MAX_MENTIONS_SCANNED`` candidates. If the cap ends the scan
    early, "more" is reported whenever the page has anything to continue from.
    """
    repo = EventRepository(db_session)
    batch = limit + 1
    rows = []
    cursor = before
    scanned = 0
    exhausted = False
    while len(rows) <= limit and scanned < MAX_MENTIONS_SCANNED:
        found = await repo.get_mention_rows(user.id, batch, cursor)
        if not found:
            exhausted = True
            break
        cursor = found[-1].event_id
        scanned += len(found)
        readable = await filter_readable_forum_ids(
            db_session, user, {row.forum_id for row in found}
        )
        rows.extend(row for row in found if row.forum_id in readable)
        if len(found) < batch:
            exhausted = True
            break

    has_more = len(rows) > limit or (not exhausted and bool(rows))
    items = [
        schemas.MentionItem(
            eventId=row.event_id,
            actor=schemas.MentionActor(id=row.actor_id, username=row.actor_username),
            threadId=row.thread_id,
            threadTitle=row.thread_title,
            postId=row.post_id,
            forumId=row.forum_id,
            createdAt=row.created_at,
            read=row.read_at is not None,
        )
        for row in rows[:limit]
    ]
    return items, has_more


async def count_unread_mentions(db_session: AsyncSession, user: User) -> int:
    """How many unread mentions the user has that they can still see: the same
    visibility as ``build_mentions``, counted over everything unread, not a page.
    The forums are grouped in the query, so the permission check is one batch over
    the distinct forums holding unread mentions."""
    by_forum = await EventRepository(db_session).count_unread_mentions_by_forum(user.id)
    readable = await filter_readable_forum_ids(db_session, user, set(by_forum))
    return sum(count for forum_id, count in by_forum.items() if forum_id in readable)
