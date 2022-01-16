if __name__ == "app":
    import django

    django.setup()


from random import seed

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# import middleware
from authorization.routes import authorization
from systems.routes import systems
from users.routes import users

# from referral_links.routes import referral_links
# from permissions.roles_routes import roles
# from permissions.permissions_routes import permissions
# from forums.forums_routes import forums

seed()


def create_app():
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
    )

    # app.before_request(middleware.initialize)
    # app.before_request(middleware.validate_jwt)

    app.include_router(authorization)
    app.include_router(systems)
    app.include_router(users)
    # app.register_blueprint(referral_links)
    # app.register_blueprint(roles)
    # app.register_blueprint(permissions)
    # app.register_blueprint(forums)

    return app
