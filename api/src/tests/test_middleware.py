import datetime
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Request

from app.configs import configs
from app.exceptions import ForbiddenException
from app.middleware import check_authorization, validate_jwt
from tests.factories import UserFactory


def make_request(headers: dict[str, str] | None = None, scope: dict | None = None) -> Request:
    raw_headers = [
        (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
    ]
    return Request(scope={"type": "http", "headers": raw_headers, **(scope or {})})


class TestValidateJwt:
    async def test_no_authorization_header_leaves_scope_unset(self, db_session):
        request = make_request()

        await validate_jwt(request, db_session)

        assert request.scope["auth"] is None
        assert request.scope["user"] is None

    async def test_non_bearer_header_leaves_scope_unset(self, db_session):
        request = make_request({"Authorization": "Basic somevalue"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] is None
        assert request.scope["user"] is None

    async def test_garbage_token_leaves_scope_unset(self, db_session):
        request = make_request({"Authorization": "Bearer not-a-real-token"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] is None
        assert request.scope["user"] is None

    async def test_wrong_signature_leaves_scope_unset(self, db_session):
        token = jwt.encode(
            {"user_id": 1}, "wrong-secret", algorithm=configs.JWT_ALGORITHM
        )
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] is None
        assert request.scope["user"] is None

    async def test_expired_token_leaves_scope_unset(self, db_session, create):
        user = await create(UserFactory)
        token = user.generate_jwt(exp_len={"seconds": -10})
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] is None
        assert request.scope["user"] is None

    async def test_unknown_user_id_leaves_scope_unset(self, db_session):
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

        assert request.scope["auth"] is None
        assert request.scope["user"] is None

    async def test_valid_token_sets_user_and_permissions(self, db_session, create):
        user = await create(UserFactory)
        token = user.generate_jwt()
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["user"].id == user.id
        assert request.scope["auth"] == []

    async def test_valid_token_updates_last_activity(self, db_session, create):
        user = await create(UserFactory)
        assert user.last_activity is None
        token = user.generate_jwt()
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["user"].last_activity is not None


class TestCheckAuthorization:
    def route_scope(self, is_public: bool, user=None) -> dict:
        endpoint = SimpleNamespace(is_public=is_public) if is_public else SimpleNamespace()
        return {"route": SimpleNamespace(endpoint=endpoint), "user": user}

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
