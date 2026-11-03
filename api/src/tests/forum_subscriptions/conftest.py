import pytest

from app.configs import configs
from app.forum_subscriptions import functions as subscription_functions
from app.models import ForumSubscription, RolePermission, UserMeta
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import PostFactory, RoleFactory, ThreadFactory

Verbs = RolePermission.ValidPermissions


@pytest.fixture(autouse=True)
async def _open_site_root(wrap_in_savepoint, open_forums):
    """Start every test with ordinary member access under the site root."""
    await open_forums(SITE_ROOT_FORUM_ID)


@pytest.fixture(autouse=True)
def _site_root(site_root_forum):
    """Forum 0's row, which forum detail pages load as an ancestor."""


@pytest.fixture(autouse=True)
def _enable_subscription_logger(monkeypatch):
    # Alembic's fileConfig (run by the test DB setup) disables loggers that
    # already existed at import time.
    monkeypatch.setattr(subscription_functions.logger, "disabled", False)


@pytest.fixture
def sent(monkeypatch):
    """Subscription emails that were sent, as ``{to, subject, content, bcc}``."""
    monkeypatch.setattr(configs, "EMAIL_ENABLED", True)
    calls = []

    async def fake_send_email(to, subject, content, **kwargs):
        calls.append({"to": to, "subject": subject, "content": content, **kwargs})

    monkeypatch.setattr(subscription_functions, "send_email", fake_send_email)
    return calls


@pytest.fixture
def subscribe(db_session):
    async def _subscribe(user, *, forum=None, thread=None):
        db_session.add(
            ForumSubscription(
                user_id=user.id,
                forum_id=forum.id if forum else None,
                thread_id=thread.id if thread else None,
            )
        )
        await db_session.flush()

    return _subscribe


@pytest.fixture
def set_mode(db_session):
    async def _set(user, value):
        db_session.add(
            UserMeta(
                user_id=user.id,
                key=UserMeta.MetaKeys.FORUM_SUB_TYPE.value,
                value=value,
            )
        )
        await db_session.flush()

    return _set


@pytest.fixture
def make_thread(create, db_session):
    """A thread with a published first post by ``author``."""

    async def _make(author, **thread_kwargs):
        thread = await create(ThreadFactory, **thread_kwargs)
        first = await create(PostFactory, thread=thread, author=author, title="Topic")
        thread.first_post_id = first.id
        thread.last_post_id = first.id
        thread.last_post_at = first.published_at
        thread.post_count = 1
        await db_session.flush()
        return thread, first

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
