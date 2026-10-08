import datetime
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Request

from app.configs import configs
from app.exceptions import BannedException, ForbiddenException, SuspendedException
from app.middleware import check_authorization, validate_jwt
from app.models import Role, RolePermission
from tests.factories import RoleFactory, UserFactory


def make_request(
    headers: dict[str, str] | None = None, scope: dict | None = None
) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(scope={"type": "http", "headers": raw_headers, **(scope or {})})


def system_role_with(db_session, monkeypatch, id_attr):
    """Build a stand-in for a system role holding the given global verbs, and
    point ``Role.<id_attr>`` at it."""

    async def _with(*verbs, effect=RolePermission.Effects.ALLOW):
        role = RoleFactory.build()
        for verb in verbs:
            role.grant(verb, effect=effect)
        db_session.add(role)
        await db_session.flush()
        monkeypatch.setattr(Role, id_attr, role.id)
        return role

    return _with


@pytest.fixture
def registered_with(db_session, monkeypatch):
    return system_role_with(db_session, monkeypatch, "REGISTERED_ID")


@pytest.fixture
def guest_with(db_session, monkeypatch):
    return system_role_with(db_session, monkeypatch, "GUEST_ID")


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
        role.grant(RolePermission.ValidPermissions.ACP_ACCESS)
        user.roles.append(role)
        await db_session.flush()
        token = user.generate_jwt()
        # Detach so validate_jwt's get_user must reload the user cold, exercising
        # the roles -> grants eager load under awaitable_attrs.
        db_session.expunge_all()
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["user"].id == user.id
        assert request.scope["auth"] == {"access_acp"}

    async def test_valid_token_adds_registered_global_grants(
        self, db_session, create, registered_with, guest_with
    ):
        await registered_with(RolePermission.ValidPermissions.ACP_ACCESS)
        await guest_with(RolePermission.ValidPermissions.ROLE_ADMIN)
        user = await create(UserFactory)
        request = make_request({"Authorization": f"Bearer {user.generate_jwt()}"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == {"access_acp"}
        assert request.scope["user"].has_global_permission("access_acp")

    async def test_registered_deny_overrides_assigned_role_allow(
        self, db_session, create, registered_with
    ):
        verb = RolePermission.ValidPermissions.ACP_ACCESS
        await registered_with(verb, effect=RolePermission.Effects.DENY)
        user = await create(UserFactory)
        role = Role(name="ACP Admins", owner=user)
        role.grant(verb)
        user.roles.append(role)
        await db_session.flush()
        request = make_request({"Authorization": f"Bearer {user.generate_jwt()}"})

        await validate_jwt(request, db_session)

        assert request.scope["auth"] == set()

    async def test_anonymous_request_gets_guest_global_grants(
        self, db_session, registered_with, guest_with
    ):
        await registered_with(RolePermission.ValidPermissions.ACP_ACCESS)
        await guest_with(RolePermission.ValidPermissions.ROLE_ADMIN)
        request = make_request()

        await validate_jwt(request, db_session)

        assert request.scope["user"] is None
        assert request.scope["auth"] == {"role_admin"}

    async def test_expired_token_gets_guest_global_grants(
        self, db_session, create, guest_with
    ):
        await guest_with(RolePermission.ValidPermissions.ROLE_ADMIN)
        user = await create(UserFactory)
        token = user.generate_jwt(exp_len={"seconds": -10})
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["user"] is None
        assert request.scope["auth"] == {"role_admin"}

    async def test_valid_token_updates_last_activity(self, db_session, create):
        user = await create(UserFactory)
        assert user.last_activity is None
        token = user.generate_jwt()
        request = make_request({"Authorization": f"Bearer {token}"})

        await validate_jwt(request, db_session)

        assert request.scope["user"].last_activity is not None


_OMIT = object()


def fake_user(block=None, suspended_until=None):
    """Stand-in user for check_authorization: only login_block matters here."""
    return SimpleNamespace(login_block=lambda: block, suspended_until=suspended_until)


class TestCheckAuthorization:
    @pytest.fixture(autouse=True)
    def _db_session(self, db_session):
        self.db_session = db_session

    async def authorize(self, request: Request):
        await check_authorization(request, self.db_session)

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

        await self.authorize(request)

    async def test_private_route_without_user_is_forbidden(self):
        request = make_request(scope=self.route_scope(is_public=False))

        with pytest.raises(ForbiddenException):
            await self.authorize(request)

    async def test_private_route_with_user_is_allowed(self):
        request = make_request(
            scope=self.route_scope(is_public=False, user=fake_user())
        )

        await self.authorize(request)

    async def test_required_permission_held_is_allowed(self):
        request = make_request(
            scope=self.route_scope(
                user=fake_user(), required=["access_acp"], auth=["access_acp"]
            )
        )

        await self.authorize(request)

    async def test_required_permission_missing_is_forbidden(self):
        request = make_request(
            scope=self.route_scope(
                user=fake_user(), required=["access_acp"], auth=["forum_moderate"]
            )
        )

        with pytest.raises(ForbiddenException):
            await self.authorize(request)

    async def test_any_one_of_the_required_permissions_suffices(self):
        request = make_request(
            scope=self.route_scope(
                user=fake_user(),
                required=["access_acp", "forum_moderate"],
                auth=["forum_moderate"],
            )
        )

        await self.authorize(request)

    async def test_admin_verb_overrides_missing_required_permission(self):
        request = make_request(
            scope=self.route_scope(
                user=fake_user(), required=["access_acp"], auth=["admin"]
            )
        )

        await self.authorize(request)

    async def test_required_permission_with_no_auth_in_scope_is_forbidden(self):
        request = make_request(
            scope=self.route_scope(user=fake_user(), required=["access_acp"])
        )

        with pytest.raises(ForbiddenException):
            await self.authorize(request)

    async def test_empty_requires_is_ignored(self):
        request = make_request(
            scope=self.route_scope(user=fake_user(), required=[], auth=[])
        )

        await self.authorize(request)

    async def test_banned_user_on_private_route_raises_banned(self):
        request = make_request(scope=self.route_scope(user=fake_user(block="banned")))

        with pytest.raises(BannedException):
            await self.authorize(request)

    async def test_suspended_user_on_private_route_raises_suspended(self):
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=1
        )
        request = make_request(
            scope=self.route_scope(
                user=fake_user(block="suspended", suspended_until=until)
            )
        )

        with pytest.raises(SuspendedException):
            await self.authorize(request)

    async def test_blocked_user_on_public_route_is_treated_as_guest(self, guest_with):
        await guest_with(RolePermission.ValidPermissions.ACP_ACCESS)
        request = make_request(
            scope=self.route_scope(
                is_public=True, user=fake_user(block="banned"), auth=["forum_moderate"]
            )
        )

        await self.authorize(request)

        assert request.scope["user"] is None
        assert request.scope["auth"] == {"access_acp"}

    async def test_blocked_user_loses_required_permission_on_public_route(self):
        request = make_request(
            scope=self.route_scope(
                is_public=True,
                user=fake_user(block="banned"),
                required=["access_acp"],
                auth=["access_acp"],
            )
        )

        with pytest.raises(ForbiddenException):
            await self.authorize(request)

    async def test_unblocked_user_on_public_route_keeps_identity(self):
        user = fake_user()
        request = make_request(
            scope=self.route_scope(is_public=True, user=user, auth=["forum_moderate"])
        )

        await self.authorize(request)

        assert request.scope["user"] is user
        assert request.scope["auth"] == {"forum_moderate"}
