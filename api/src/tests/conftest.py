from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import URL

load_dotenv(Path(__file__).parent.parent.parent / ".env.test", override=True)

from tests.factories import ActivatedUserFactory, ForumFactory, RoleFactory

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from alembic import command
from app.configs import configs
from app.database import get_db_session, get_legacy_db_session, session_manager
from app.main import create_app
from app.models import Role, RolePermission, User


@pytest.fixture(scope="session", autouse=True)
def fast_bcrypt():
    """Use bcrypt's minimum cost factor for the test process only.

    Production code always calls bcrypt.gensalt() with its real default
    (12 rounds); there is no env var or config path that could carry a
    weakened cost factor into a non-test environment. 4 is the lowest
    value bcrypt allows (ValueError below that).
    """
    original_gensalt = bcrypt.gensalt
    bcrypt.gensalt = lambda *args, **kwargs: original_gensalt(rounds=4)
    yield
    bcrypt.gensalt = original_gensalt


@pytest.fixture(scope="session")
def alembic_cfg():
    url = URL.create(
        drivername="postgresql+psycopg",
        username=configs.DATABASE_USER,
        password=configs.DATABASE_PASSWORD,
        host=configs.DATABASE_HOST,
        port=configs.DATABASE_PORT,
        database=f"{configs.DATABASE_DATABASE}",
    )
    cfg = Config(Path(__file__).parent.parent / "alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.set_main_option(
        "script_location", str(Path(__file__).parent.parent / "alembic")
    )
    cfg.set_main_option("environment", "test")
    return cfg


@pytest.fixture(scope="session", autouse=True)
def run_migrations(alembic_cfg):
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session")
async def test_engine():
    session_manager.init(
        host=configs.DATABASE_HOST,
        port=configs.DATABASE_PORT,
        user=configs.DATABASE_USER,
        password=configs.DATABASE_PASSWORD,
        database=f"{configs.DATABASE_DATABASE}",
    )
    yield session_manager._engine
    await session_manager.close()


@pytest.fixture(scope="session")
async def db_connection(test_engine):
    async with test_engine.connect() as conn:
        await conn.begin()
        yield conn
        await conn.rollback()


@pytest.fixture(scope="session")
async def db_session(db_connection):
    session_factory = async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()
    yield session
    await session.close()


@pytest.fixture(autouse=False)
async def wrap_in_savepoint(db_connection, db_session):
    """Roll back to a savepoint after each test to keep data isolation."""
    await db_connection.begin_nested()
    yield
    await db_connection.rollback()
    db_session.expunge_all()


@pytest.fixture(scope="function")
async def client(db_session, wrap_in_savepoint):
    app = create_app(init_db=False)

    async def override_get_db_session():
        yield db_session

    async def override_get_legacy_db_session():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_legacy_db_session] = override_get_legacy_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def create(db_session):
    async def _create(factory, **kwargs):
        instance = factory.build(**kwargs)
        db_session.add(instance)
        await db_session.flush()
        return instance

    return _create


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.begin = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=None),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    mock_result = MagicMock()
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
def mock_session_manager(mock_session):
    with patch("app.bgg.scheduler.session_manager") as mock_sm:
        mock_sm.session.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=False),
        )
        yield mock_session


@pytest.fixture
def auth_as(client):
    """Point the shared test client at a given user's bearer token."""

    def _auth_as(user):
        client.headers["Authorization"] = f"Bearer {user.generate_jwt()}"
        return client

    return _auth_as


@pytest.fixture
async def authed_client(client, create, auth_as):
    user = await create(ActivatedUserFactory)
    auth_as(user)
    return client, user


# Forum id every real forum descends from. Tests can put a forum under it via
# heritage without creating the row, since the resolver only needs the id.
SITE_ROOT_FORUM_ID = 0


@pytest.fixture
async def site_root_forum(create, wrap_in_savepoint):
    """The real forum 0 row, for tests that register users (registration seeds
    their read tracking on it). Opt-in: other tests get by without the row, and
    some create it themselves."""
    return await create(ForumFactory, id=SITE_ROOT_FORUM_ID, heritage=[])


MEMBER_VERBS = (
    RolePermission.ValidPermissions.FORUM_READ,
    RolePermission.ValidPermissions.FORUM_WRITE,
    RolePermission.ValidPermissions.FORUM_EDIT,
    RolePermission.ValidPermissions.FORUM_DELETE,
    RolePermission.ValidPermissions.FORUM_CREATE_THREAD,
    RolePermission.ValidPermissions.FORUM_DELETE_THREAD,
)


@pytest.fixture(autouse=True)
def unseeded_system_roles(monkeypatch):
    """Point Registered/Guest at ids no role has.

    Rolled-back tests don't rewind the roles sequence, so without this a role a
    test creates could land on id 2 or 3 and be granted to everyone implicitly.
    ``open_forums`` (or a test) repoints them at real roles.
    """
    monkeypatch.setattr(Role, "REGISTERED_ID", -1)
    monkeypatch.setattr(Role, "GUEST_ID", -1)
    # Built from the real ids at import, so it needs emptying too.
    monkeypatch.setattr(
        "app.repositories.rbac_repository.IMPLICIT_ROLE_IDS", frozenset()
    )


@pytest.fixture
async def fallback_owner(create, monkeypatch):
    """A persisted user standing in for ``User.FALLBACK_OWNER_ID`` (user 1 in
    production, which test users never get), so handing a role back to the
    fallback owner doesn't violate the owner foreign key. Opt-in."""
    owner = await create(ActivatedUserFactory)
    monkeypatch.setattr(User, "FALLBACK_OWNER_ID", owner.id)
    return owner


@pytest.fixture
def sent_webhooks(monkeypatch):
    """Replace the Discord sender with a recorder, so no test calls Discord.

    The list fills with ``(url, payload)`` as each queued background task runs.
    """
    sent: list[tuple[str, dict]] = []

    async def record(url, payload):
        sent.append((url, payload))

    monkeypatch.setattr("app.threads.discord.send_webhook", record)
    return sent


@pytest.fixture
def open_forums(db_session, monkeypatch):
    """Give Registered users member access, and Guests read access, to forums.

    Builds stand-ins for the Registered/Guest roles and repoints ``Role``'s ids
    at them (forcing the real ids 2/3 past the shared sequence isn't practical).
    Call it once per test.
    """

    async def _open_forums(*forum_ids):
        registered = RoleFactory.build()
        guest = RoleFactory.build()
        db_session.add_all([registered, guest])
        for forum_id in forum_ids:
            scope = {
                "scope_type": RolePermission.ScopeTypes.FORUM,
                "scope_id": forum_id,
            }
            for verb in MEMBER_VERBS:
                registered.grant(verb, **scope)
            guest.grant(RolePermission.ValidPermissions.FORUM_READ, **scope)
        await db_session.flush()
        monkeypatch.setattr(Role, "REGISTERED_ID", registered.id)
        monkeypatch.setattr(Role, "GUEST_ID", guest.id)
        return registered, guest

    return _open_forums
