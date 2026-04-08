import contextlib
from typing import Annotated, AsyncIterator, Literal

import paramiko
from fastapi import Depends
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sshtunnel import SSHTunnelForwarder


class DatabaseSessionManager:
    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None
        self._tunnel: SSHTunnelForwarder | None = None

    def init(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        dialect: Literal["postgresql", "mysql"] = "postgresql",
        ssh_config: dict | None = None,
    ):
        target_host = host
        target_port = port

        if ssh_config:
            self._tunnel = SSHTunnelForwarder(
                (host, 22),
                ssh_username=ssh_config["ssh_user"],
                ssh_pkey=paramiko.Ed25519Key.from_private_key_file(
                    ssh_config["ssh_pkey"]
                ),
                remote_bind_address=("localhost", target_port),
                set_keepalive=30.0,
                # host_pkey_directories=[],
            )
            self._tunnel.start()

            target_host = "localhost"
            target_port = self._tunnel.local_bind_port

        if dialect == "postgresql":
            driver = "asyncpg"
        elif dialect == "mysql":
            driver = "aiomysql"

        db_url = URL.create(
            drivername=f"{dialect}+{driver}",
            username=user,
            password=password,
            host=target_host,
            port=target_port,
            database=database,
        )

        self._engine: AsyncEngine | None = create_async_engine(
            db_url,
            pool_recycle=3600,
            pool_pre_ping=True,
            pool_use_lifo=True,
        )
        self._sessionmaker: async_sessionmaker | None = async_sessionmaker(
            bind=self._engine, autocommit=False, expire_on_commit=False, autoflush=False
        )

    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        await self._engine.dispose()

        if self._tunnel is not None:
            self._tunnel.stop()

        self._engine = None
        self._sessionmaker = None
        self._tunnel = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


session_manager = DatabaseSessionManager()


async def get_db_session():
    async with session_manager.session() as session:
        yield session


DBSessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
