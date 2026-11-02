import logging
from dataclasses import dataclass
from enum import StrEnum

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.forums.functions import filter_readable_forum_ids
from app.forums.permissions import ForumPermissions, Verbs
from app.forum_subscriptions import schemas
from app.helpers.email import get_template, send_email
from app.models import Forum, Post, Thread, User
from app.repositories import ForumRepository, ForumSubscriptionRepository
from app.repositories.forum_repository import SITE_ROOT_FORUM_ID
from app.repositories.forum_subscription_repository import SubscriptionKind

logger = logging.getLogger(__name__)

NOTICE_TEMPLATE = "forum_subscriptions/templates/subscription_notice.html"


class Trigger(StrEnum):
    NEW_THREAD = "new_thread"
    NEW_POST = "new_post"
    EDIT = "edit"


@dataclass(frozen=True)
class Recipient:
    user_id: int
    email: str
    mode: str  # "all" or "new content"
    kind: SubscriptionKind


def _plain(title: str) -> str:
    # Titles are stored with newlines as <br>
    return title.replace("<br>", " ")


async def select_recipients(
    db_session: AsyncSession,
    thread: Thread,
    forum: Forum,
    post: Post,
    actor: User,
    trigger: Trigger,
) -> list[Recipient]:
    """Who should be emailed about ``post`` (a new thread's first post, a reply, or
    a non-minor edit of a post in ``thread``).

    Subscribers are the thread's and its forum's own (direct) subscribers, minus
    the actor, minus anyone who can't be mailed or can't read the forum right now.
    By forumSubType: "none" never; "all" always; "new content" only for a new thread
    or reply, and only when due a notice (``users_due_notice``), so an edit never
    reaches them. Unpublished content (drafts, revisions) emails nobody.
    """
    if post.state != Post.States.PUBLISHED or post.published_at is None:
        return []
    if thread.deleted is not None:
        return []

    repo = ForumSubscriptionRepository(db_session)
    kinds = await repo.subscribers(thread)
    kinds.pop(actor.id, None)

    candidates = [
        (user, mode)
        for user, mode in await repo.deliverable_users(kinds)
        if mode == "all" or (mode == "new content" and trigger is not Trigger.EDIT)
    ]
    due = await repo.users_due_notice(
        thread, {user.id for user, mode in candidates if mode == "new content"}
    )

    recipients = []
    for user, mode in candidates:
        if mode == "new content" and user.id not in due:
            continue
        # One lookup per remaining subscriber: permissions are per user and, with
        # roles and player mode involved, aren't worth re-deriving in bulk here.
        permissions = await ForumPermissions.load(db_session, user, [forum])
        if permissions.has(forum, Verbs.FORUM_READ):
            recipients.append(Recipient(user.id, user.email, mode, kinds[user.id]))
    return recipients


async def send_subscription_email(
    emails: list[str],
    *,
    mode: str,
    kind: str,
    trigger: str,
    actor_username: str,
    thread_id: int,
    thread_title: str,
    forum_id: int,
    forum_title: str,
    post_id: int,
) -> None:
    """Mail one group of recipients (BCC) the same notice. Takes plain values only:
    it runs as a background task, after the request's DB session is gone. The
    notice never carries any post content, and a "new content" notice doesn't name
    the actor."""
    thread_title = _plain(thread_title)
    forum_title = _plain(forum_title)
    if mode == "all":
        headline = "Thread Update"
        if trigger == Trigger.NEW_THREAD:
            subject = f"New thread in {forum_title}: {thread_title}"
        elif trigger == Trigger.EDIT:
            subject = f'Post edited in "{thread_title}"'
        else:
            subject = f'New post in "{thread_title}"'
    elif kind == "thread":
        headline = "Thread Update"
        subject = f'New activity in the thread "{thread_title}"'
    else:
        headline = "Forum Update"
        subject = f"New activity in the {forum_title} forum"
    content = get_template(
        NOTICE_TEMPLATE,
        mode=mode,
        kind=kind,
        trigger=str(trigger),
        headline=headline,
        # Only the "all" notice names who did it.
        actor=actor_username if mode == "all" else "",
        thread_id=thread_id,
        thread_title=thread_title,
        forum_id=forum_id,
        forum_title=forum_title,
        post_id=post_id,
    )
    await send_email(configs.CONTACT_EMAIL, subject, content, bcc=emails, mass=True)


async def queue_subscription_emails(
    background_tasks: BackgroundTasks,
    db_session: AsyncSession,
    thread: Thread,
    post: Post,
    actor: User,
    trigger: Trigger,
) -> None:
    """Email the subscribers of a new thread, a new reply or a (non-minor) edit,
    and note the "new content" subscribers who were mailed. Resolves everything
    now, inside the request, and schedules one message per (mode, subscription
    kind) group."""
    if not configs.EMAIL_ENABLED:
        logger.info("Email disabled; would have mailed subscribers of post %s", post.id)
        return
    # Looked up by id: a thread created in this request hasn't loaded these.
    forum = await db_session.get(Forum, thread.forum_id)
    assert forum is not None
    recipients = await select_recipients(
        db_session, thread, forum, post, actor, trigger
    )
    if not recipients:
        return

    if trigger is not Trigger.EDIT:
        assert post.published_at is not None
        await ForumSubscriptionRepository(db_session).record_notices(
            thread,
            [r.user_id for r in recipients if r.mode == "new content"],
            post.published_at,
        )

    first_post = (
        post
        if post.id == thread.first_post_id
        else await db_session.get(Post, thread.first_post_id)
    )
    assert first_post is not None

    groups: dict[tuple[str, str], list[str]] = {}
    for recipient in recipients:
        groups.setdefault((recipient.mode, recipient.kind), []).append(recipient.email)
    for (mode, kind), emails in groups.items():
        background_tasks.add_task(
            send_subscription_email,
            emails,
            mode=mode,
            kind=kind,
            trigger=str(trigger),
            actor_username=actor.username,
            thread_id=thread.id,
            thread_title=first_post.title,
            forum_id=forum.id,
            forum_title=forum.title,
            post_id=post.id,
        )


async def build_subscriptions(
    db_session: AsyncSession, user: User
) -> schemas.GetSubscriptionsResponse:
    """The user's subscriptions for the Manage Subscriptions page, leaving out
    forums and threads they can't read now (those stay subscribed)."""
    repo = ForumSubscriptionRepository(db_session)
    forum_ids, thread_ids = await repo.get_for_user(user.id)
    threads = [
        thread
        for thread in await repo.get_subscribed_threads(thread_ids)
        if thread.first_post is not None
    ]
    readable = await filter_readable_forum_ids(
        db_session, user, {*forum_ids, *(thread.forum_id for thread in threads)}
    )

    forum_repository = ForumRepository(db_session, principal=user)
    subscribed_forums = list(
        await forum_repository.get_multiple([f for f in forum_ids if f in readable])
    )
    # Ancestors come along as headings so a subscribed subforum has its parents.
    ancestor_ids = {
        ancestor_id
        for forum in subscribed_forums
        for ancestor_id in forum.heritage
        if ancestor_id != SITE_ROOT_FORUM_ID
    } - {forum.id for forum in subscribed_forums}
    ancestors = (
        list(await forum_repository.get_multiple(list(ancestor_ids)))
        if ancestor_ids
        else []
    )
    forums = [
        schemas.SubscribedForum(
            id=forum.id,
            title=forum.title,
            parent_id=None
            if forum.parent_id == SITE_ROOT_FORUM_ID
            else forum.parent_id,
            subscribed=forum.id in forum_ids,
        )
        for forum in sorted(
            [*subscribed_forums, *ancestors], key=lambda forum: forum.order
        )
    ]

    groups: dict[int, schemas.SubscribedThreadGroup] = {}
    for thread in sorted(threads, key=lambda thread: thread.id):
        if thread.forum_id not in readable:
            continue
        assert thread.first_post is not None
        group = groups.setdefault(
            thread.forum_id,
            schemas.SubscribedThreadGroup(
                forum_id=thread.forum_id, forum_title=thread.forum.title, threads=[]
            ),
        )
        group.threads.append(
            schemas.SubscribedThread(id=thread.id, title=thread.first_post.title)
        )
    return schemas.GetSubscriptionsResponse(
        forums=forums, thread_groups=sorted(groups.values(), key=lambda g: g.forum_id)
    )
