import pytest
from sqlalchemy import func, select

from app.models import Event, EventRecipient, RolePermission
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ActivatedUserFactory,
    PostFactory,
    RoleFactory,
    ThreadFactory,
)


@pytest.fixture(autouse=True)
async def _open_site_root(wrap_in_savepoint, open_forums, db_session):
    """Start every test with ordinary member access under the site root, and fail
    loudly if an earlier test leaked events (these tests count on a clean table)."""
    leaked = await db_session.scalar(select(func.count()).select_from(Event))
    assert leaked == 0, "events leaked from an earlier test"
    await open_forums(SITE_ROOT_FORUM_ID)


@pytest.fixture
async def author(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def thread(create):
    return await create(ThreadFactory)


@pytest.fixture
def make_post(create):
    """A published post in the thread, as a first post (so the thread has a title)
    if it is the thread's first."""

    async def _make(thread, author, body, **kwargs):
        post = await create(
            PostFactory, thread=thread, author=author, body=body, **kwargs
        )
        if thread.first_post_id is None:
            thread.first_post_id = post.id
            thread.last_post_id = post.id
            thread.last_post_at = post.published_at
            thread.post_count = 1
        return post

    return _make


@pytest.fixture
def grant(db_session):
    """Give ``user`` a role holding ``verbs`` on ``forum``."""

    async def _grant(user, forum, *verbs):
        role = RoleFactory.build()
        db_session.add(role)
        for verb in verbs:
            role.grant(
                verb, scope_type=RolePermission.ScopeTypes.FORUM, scope_id=forum.id
            )
        role.users.append(user)
        await db_session.flush()

    return _grant


@pytest.fixture
def recipients(db_session):
    """The user ids with a row for the post's mention event, or None when the post
    has no event."""

    async def _recipients(post):
        event = await db_session.scalar(select(Event).where(Event.post_id == post.id))
        if event is None:
            return None
        rows = await db_session.scalars(
            select(EventRecipient.user_id).where(EventRecipient.event_id == event.id)
        )
        return set(rows)

    return _recipients
