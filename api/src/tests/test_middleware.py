import datetime
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Request

from app.configs import configs
from app.exceptions import ForbiddenException
from app.middleware import check_authorization, validate_jwt
from app.models import Permission, Role
from tests.factories import UserFactory


def make_request(
    headers: dict[str, str] | None = None, scope: dict | None = None
) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(scope={"type": "http", "headers": raw_headers, **(scope or {})})


class TestValidateJwt:
    async def test_no_authorization_header_defaults_to_unauthenticated(
        self, db_session
    ):
        request = make_request()

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == set()
        assert request.scope["user"] is None

    async def test_non_bearer_header_defaults_to_unauthenticated(self, db_session):
        request = make_request({"Authorization": "Basic somevalue"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == set()
        assert request.scope["user"] is None

    async def test_garbage_token_defaults_to_unauthenticated(self, db_session):
        request = make_request({"Authorization": "Bearer not-a-real-token"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == set()
        assert request.scope["user"] is None

    async def test_wrong_signature_defaults_to_unauthenticated(self, db_session):
        token = jwt.encode(
            {"user_id": 1}, "wrong-secret", algorithm=configs.JWT_ALGORITHM
        )
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == set()
        assert request.scope["user"] is None

    async def test_expired_token_defaults_to_unauthenticated(self, db_session, create):
        user = await create(UserFactory)
        token = user.generate_jwt(exp_len={"seconds": -10})
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == set()
        assert request.scope["user"] is None

    async def test_unknown_user_id_defaults_to_unauthenticated(self, db_session):
        token = jwt.encode(
            {
                "user_id": 0,
                "exp": datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(weeks=1),
            },
            configs.JWT_SECRET_KEY,
            algorithm=configs.JWT_ALGORITHM,
        )
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == set()
        assert request.scope["user"] is None

    async def test_valid_token_sets_user_and_global_permissions(
        self, db_session, create, wrap_in_savepoint
    ):
        user = await create(UserFactory)
        role = Role(name="ACP Admins", owner=user)
        role.grant(Permission(permission="access_acp"))
        user.roles.append(role)
        await db_session.flush()
        token = user.generate_jwt()
        # Detach so validate_jwt's get_user must reload the user cold, exercising
        # the roles -> grants -> permission eager load under awaitable_attrs.
        db_session.expunge_all()
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["user"].id == user.id
        assert request.scope["auth"] == {"access_acp"}

    async def test_valid_token_updates_last_activity(self, db_session, create):
        user = await create(UserFactory)
        assert user.last_activity is None
        token = user.generate_jwt()
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["user"].last_activity is not None


_OMIT = object()


class TestCheckAuthorization:
    def route_scope(
        self, is_public=False, user=None, required=None, auth=_OMIT
    ) -> dict:
        endpoint = SimpleNamespace()
        if is_public:
            endpoint.is_public = True
        if required is not None:
            endpoint.required_permissions = frozenset(required)
        scope = {"route": SimpleNamespace(endpoint=endpoint), "user": user}
        if auth is not _OMIT:
            scope["auth"] = None if auth is None else set(auth)
        return scope

    async def test_public_route_without_user_is_allowed(self):
        request = make_request(scope=self.route_scope(is_public=True))

        await check_authorization(request)

    async def test_public_route_with_user_is_allowed(self):
        request = make_request(scope=self.route_scope(is_public=True, user=object()))

        await check_authorization(request)

    async def test_private_route_without_user_is_forbidden(self):
        request = make_request(scope=self.route_scope(is_public=False))

        with pytest.raises(ForbiddenException):
            await check_authorization(request)

    async def test_private_route_with_user_is_allowed(self):
        request = make_request(scope=self.route_scope(is_public=False, user=object()))

        await check_authorization(request)

    async def test_required_permission_held_is_allowed(self):
        request = make_request(
            scope=self.route_scope(
                user=object(), required=["access_acp"], auth=["access_acp"]
            )
        )

        await check_authorization(request)

    async def test_required_permission_missing_is_forbidden(self):
        request = make_request(
            scope=self.route_scope(
                user=object(), required=["access_acp"], auth=["moderate_forum"]
            )
        )

        with pytest.raises(ForbiddenException):
            await check_authorization(request)

    async def test_any_one_of_the_required_permissions_suffices(self):
        request = make_request(
            scope=self.route_scope(
                user=object(),
                required=["access_acp", "moderate_forum"],
                auth=["moderate_forum"],
            )
        )

        await check_authorization(request)

    async def test_admin_verb_overrides_missing_required_permission(self):
        request = make_request(
            scope=self.route_scope(
                user=object(), required=["access_acp"], auth=["admin"]
            )
        )

        await check_authorization(request)

    async def test_required_permission_with_no_auth_in_scope_is_forbidden(self):
        request = make_request(
            scope=self.route_scope(user=object(), required=["access_acp"])
        )

        with pytest.raises(ForbiddenException):
            await check_authorization(request)

    async def test_empty_requires_is_ignored(self):
        request = make_request(
            scope=self.route_scope(user=object(), required=[], auth=[])
        )

        await check_authorization(request)
