from contextlib import asynccontextmanager
from random import seed

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import middleware
from app.auth.routes import auth
from app.configs import configs
from app.database import get_db_session, session_manager

# from forums.forums_routes import forums
# from permissions.roles_routes import roles
# from referral_links.routes import referral_links
# from systems.routes import systems
from app.users.routes import users

# from permissions.permissions_routes import permissions

seed()


def create_app(init_db=True) -> FastAPI:
    if init_db:
        session_manager.init(
            host=configs.DATABASE_HOST,
            user=configs.DATABASE_USER,
            password=configs.DATABASE_PASSWORD,
            database=configs.DATABASE_DATABASE,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if init_db and session_manager._engine is not None:
            await session_manager.close()

    app = FastAPI(
        dependencies=[
            Depends(middleware.validate_jwt),
            Depends(get_db_session),
            Depends(middleware.check_authorization),
        ],
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
    )

    app.include_router(auth)
    # app.include_router(forums)
    # app.include_router(permissions)
    # app.include_router(referral_links)
    # app.include_router(roles)
    # app.include_router(systems)
    app.include_router(users)

    return app
