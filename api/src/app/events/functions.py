from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.events import schemas
from app.forums.functions import filter_readable_forum_ids
from app.forums.permissions import ForumPermissions, Verbs
from app.helpers.prose import mentioned_user_ids
from app.models import Event, Forum, Post, Thread, User
from app.repositories import EventRepository, PlayerRepository

# Most candidate notifications looked at to fill one page. Mentions in forums the
# user can no longer read are dropped after the query, so a page can need more than
# one batch; this keeps a long hidden history from turning into an unbounded scan.
MAX_NOTIFICATIONS_SCANNED = 500


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


def _build_notification(row) -> schemas.Notification:
    common = {
        "eventId": row.event_id,
        "actor": schemas.NotificationActor(
            id=row.actor_id, username=row.actor_username
        ),
        "createdAt": row.created_at,
        "read": row.read_at is not None,
    }
    match row.type:
        case Event.Types.MENTION:
            return schemas.MentionNotification(
                **common,
                threadId=row.thread_id,
                threadTitle=row.thread_title,
                postId=row.post_id,
                forumId=row.forum_id,
            )
        case Event.Types.GAME_INVITE:
            return schemas.GameInviteNotification(
                **common, gameId=row.game_id, gameTitle=row.game_title
            )
        case Event.Types.GAME_APPLICATION:
            return schemas.GameApplicationNotification(
                **common, gameId=row.game_id, gameTitle=row.game_title
            )
        case Event.Types.CHARACTER_SUBMITTED:
            return schemas.CharacterSubmittedNotification(
                **common,
                gameId=row.game_id,
                gameTitle=row.game_title,
                characterId=row.character_id,
                characterName=row.character_name or "",
            )
    raise ValueError(f"Unknown event type {row.type}")


async def build_notifications(
    db_session: AsyncSession,
    user: User,
    limit: int,
    before: tuple[datetime, int] | None,
) -> tuple[list[schemas.Notification], bool, str | None]:
    """A page of the user's notifications of every type, newest first (the ones
    after the ``(created_at, event id)`` key ``before``), whether there are more
    after it, and the cursor that continues from it. Anything whose underlying
    state no longer holds is left out (see ``EventRepository``), as are mentions
    in forums the user can't read now.

    Candidates come in batches of ``limit + 1`` until that many visible ones are
    found, up to ``MAX_NOTIFICATIONS_SCANNED`` candidates. If the cap ends the
    scan early, "more" is reported whenever the page has anything to continue from.
    """
    repo = EventRepository(db_session)
    batch = limit + 1
    rows = []
    cursor = before
    scanned = 0
    exhausted = False
    while len(rows) <= limit and scanned < MAX_NOTIFICATIONS_SCANNED:
        found = await repo.get_notification_rows(user.id, batch, cursor)
        if not found:
            exhausted = True
            break
        cursor = (found[-1].created_at, found[-1].event_id)
        scanned += len(found)
        readable = await filter_readable_forum_ids(
            db_session, user, {row.forum_id for row in found if row.forum_id}
        )
        rows.extend(
            row for row in found if row.forum_id is None or row.forum_id in readable
        )
        if len(found) < batch:
            exhausted = True
            break

    has_more = len(rows) > limit or (not exhausted and bool(rows))
    page = rows[:limit]
    next_cursor = (
        repo.cursor_for(page[-1].created_at, page[-1].event_id)
        if has_more and page
        else None
    )
    return [_build_notification(row) for row in page], has_more, next_cursor


async def count_unread_notifications(db_session: AsyncSession, user: User) -> int:
    """How many unread notifications the user has that they can still see: the
    same visibility as ``build_notifications``, counted over everything unread, not
    a page. The forums are grouped in the query, so the permission check is one
    batch over the distinct forums holding unread mentions."""
    by_forum = await EventRepository(db_session).count_unread_by_forum(user.id)
    readable = await filter_readable_forum_ids(
        db_session, user, {forum_id for forum_id in by_forum if forum_id is not None}
    )
    return sum(
        count
        for forum_id, count in by_forum.items()
        if forum_id is None or forum_id in readable
    )


# Game events


async def _notify_game_gms(
    db_session: AsyncSession,
    actor: User,
    type: Event.Types,
    game_id: int,
    *,
    subject_user_id: int | None = None,
    character_id: int | None = None,
) -> None:
    """Raise the event for the game's GMs (the actor aside) who can be notified."""
    gm_ids = set(
        await PlayerRepository(db_session, principal=actor).get_gm_ids(game_id)
    )
    repo = EventRepository(db_session)
    gms = await repo.get_notifiable_users(gm_ids - {actor.id})
    await repo.upsert_event(
        type,
        actor.id,
        {gm.id for gm in gms},
        game_id=game_id,
        subject_user_id=subject_user_id,
        character_id=character_id,
    )


async def notify_game_invite(
    db_session: AsyncSession, actor: User, game_id: int, invitee_id: int
) -> None:
    """Tell the invitee the actor (a GM) invited them to the game, unless they
    can't be notified. Inviting again reuses and re-raises the event."""
    repo = EventRepository(db_session)
    invitees = await repo.get_notifiable_users({invitee_id})
    await repo.upsert_event(
        Event.Types.GAME_INVITE,
        actor.id,
        {user.id for user in invitees},
        game_id=game_id,
        subject_user_id=invitee_id,
    )


async def notify_game_application(
    db_session: AsyncSession, applicant: User, game_id: int
) -> None:
    """Tell the game's GMs the applicant applied."""
    await _notify_game_gms(
        db_session,
        applicant,
        Event.Types.GAME_APPLICATION,
        game_id,
        subject_user_id=applicant.id,
    )


async def notify_character_submitted(
    db_session: AsyncSession, owner: User, game_id: int, character_id: int
) -> None:
    """Tell the game's GMs the owner submitted a character for approval."""
    await _notify_game_gms(
        db_session,
        owner,
        Event.Types.CHARACTER_SUBMITTED,
        game_id,
        character_id=character_id,
    )
