from contextlib import asynccontextmanager
from pathlib import Path
from random import seed

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import middleware
from app.auth.legacy_routes import auth as legacy_auth
from app.configs import configs
from app.database import (
    get_db_session,
    get_legacy_db_session,
    legacy_session_manager,
    session_manager,
)
from app.gamers.legacy_routes import gamers as legacy_gamers
from app.me.legacy_routes import me as legacy_me
from app.pms.legacy_routes import pms as legacy_pms
from app.referral_links.routes import referral_links
from app.systems.legacy_routes import systems as legacy_systems

seed()

if configs.ENVIRONMENT == "dev":
    from icecream.builtins import install

    install()


def create_app(init_db=True) -> FastAPI:
    if init_db:
        ssh_config = {}
        if (
            configs.DATABASE_SSH_USERNAME
            and configs.DATABASE_SSH_PKEY
            and Path(configs.DATABASE_SSH_PKEY).exists()
        ):
            ssh_config = {
                "ssh_user": configs.DATABASE_SSH_USERNAME,
                "ssh_pkey": configs.DATABASE_SSH_PKEY,
            }
        session_manager.init(
            host=configs.DATABASE_HOST,
            port=configs.DATABASE_PORT,
            user=configs.DATABASE_USER,
            password=configs.DATABASE_PASSWORD,
            database=configs.DATABASE_DATABASE,
            dialect=configs.DATABASE_DIALECT,
            ssh_config=ssh_config,
        )

        legacy_ssh_config = {}
        if (
            configs.LEGACY_DATABASE_SSH_USERNAME
            and configs.LEGACY_DATABASE_SSH_PKEY
            and Path(configs.LEGACY_DATABASE_SSH_PKEY).exists()
        ):
            legacy_ssh_config = {
                "ssh_user": configs.LEGACY_DATABASE_SSH_USERNAME,
                "ssh_pkey": configs.LEGACY_DATABASE_SSH_PKEY,
            }
        legacy_session_manager.init(
            host=configs.LEGACY_DATABASE_HOST,
            port=configs.LEGACY_DATABASE_PORT,
            user=configs.LEGACY_DATABASE_USER,
            password=configs.LEGACY_DATABASE_PASSWORD,
            database=configs.LEGACY_DATABASE_DATABASE,
            dialect=configs.LEGACY_DATABASE_DIALECT,
            ssh_config=legacy_ssh_config,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if init_db:
            if session_manager._engine is not None:
                await session_manager.close()
            if legacy_session_manager._engine is not None:
                await legacy_session_manager.close()

    app = FastAPI(
        dependencies=[
            # Depends(middleware.validate_jwt),
            Depends(middleware.validate_cookie),
            Depends(get_db_session),
            Depends(get_legacy_db_session),
            Depends(middleware.check_authorization),
        ],
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[configs.HOST_NAME, configs.V1_HOST_NAME],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # app.include_router(auth)
    app.include_router(legacy_auth)
    app.include_router(legacy_me)
    app.include_router(legacy_gamers)
    app.include_router(legacy_pms)
    app.include_router(legacy_systems)

    app.include_router(referral_links)

    return app
