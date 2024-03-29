if __name__ == "app":
    import django

    django.setup()


from random import seed

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import middleware
from authorization.routes import authorization
from forums.forums_routes import forums
from permissions.roles_routes import roles
from referral_links.routes import referral_links
from systems.routes import systems
from users.routes import users

# from permissions.permissions_routes import permissions

seed()


def create_app():
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
    )

    app.add_middleware(
        BaseHTTPMiddleware,
        dispatch=middleware.validate_jwt,
    )

    app.include_router(authorization)
    app.include_router(forums)
    # app.include_router(permissions)
    app.include_router(referral_links)
    app.include_router(roles)
    app.include_router(systems)
    app.include_router(users)

    return app
