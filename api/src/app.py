from random import seed

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import middleware
from auth.routes import auth
from database import get_db_session

# from forums.forums_routes import forums
# from permissions.roles_routes import roles
# from referral_links.routes import referral_links
# from systems.routes import systems
# from users.routes import users

# from permissions.permissions_routes import permissions

seed()


def create_app():
    app = FastAPI(
        dependencies=[
            Depends(get_db_session),
            Depends(middleware.check_authorization),
        ]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
    )

    app.add_middleware(
        BaseHTTPMiddleware,
        dispatch=middleware.validate_jwt,
    )

    app.include_router(auth)
    # app.include_router(forums)
    # app.include_router(permissions)
    # app.include_router(referral_links)
    # app.include_router(roles)
    # app.include_router(systems)
    # app.include_router(users)

    return app
