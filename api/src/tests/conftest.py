import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.configs import configs
from app.database import get_db_session, session_manager
from app.main import create_app
from app.models.base import Base


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def app():
    yield create_app(init_db=False)


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture(scope="function", autouse=True)
async def db_connection():
    session_manager.init(
        host=configs.DATABASE_HOST,
        user=configs.DATABASE_USER,
        password=configs.DATABASE_PASSWORD,
        database=f"{configs.DATABASE_DATABASE}_test",
    )
    yield
    await session_manager.close()


@pytest.fixture(scope="function", autouse=True)
async def create_tables(db_connection):
    async with session_manager.connect() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="function")
async def db_session(db_connection):
    async with session_manager.session() as session:
        yield session


@pytest.fixture(scope="function", autouse=True)
async def session_override(app, db_connection, db_session):
    async def get_db_override():
        yield db_session

    app.dependency_overrides[get_db_session] = get_db_override


@pytest.fixture(scope="function", autouse=True)
def reset_configs():
    configs.from_env()
