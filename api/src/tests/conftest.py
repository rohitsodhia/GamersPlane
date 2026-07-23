from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from dotenv import load_dotenv
from sqlalchemy import URL

from tests.factories import ActivatedUserFactory

load_dotenv(Path(__file__).parent.parent.parent / ".env.test", override=True)

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from alembic import command
from app.configs import configs
from app.database import get_db_session, session_manager
from app.main import create_app


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
async def wrap_in_savepoint(db_connection):
    """Roll back to a savepoint after each test to keep data isolation."""
    await db_connection.begin_nested()
    yield
    await db_connection.rollback()


@pytest.fixture(scope="function")
async def client(db_session, wrap_in_savepoint):
    app = create_app(init_db=False)

    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

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
async def authed_client(client, create):
    user = await create(ActivatedUserFactory)
    token = user.generate_jwt()
    client.headers["Authorization"] = f"Bearer {token}"
    return client, user
