from datetime import datetime, timedelta, timezone

import pytest

from app.models import Role, RolePermission, User, UserMeta
from tests.factories import UserFactory


class TestValidatePassword:
    @pytest.mark.parametrize(
        ("password", "expected_codes"),
        [("short1", ["pass_too_short"]), ("LongEnough1", [])],
    )
    def test_validates_length(self, password, expected_codes):
        errors = User.validate_password(password)

        assert [e.code for e in errors] == expected_codes


class TestSetPassword:
    def test_valid_password_hashes_and_returns_true(self):
        user = User(username="test", email="test@example.com")

        result = user.set_password("ValidPass1!")

        assert result is True
        assert user.check_pass("ValidPass1!")

    def test_invalid_password_returns_false_and_leaves_password_unset(self):
        user = User(username="test", email="test@example.com")

        result = user.set_password("short")

        assert result is False
        assert user.password is None


class TestLoginBlock:
    async def test_clean_user_is_not_blocked(self, create):
        user = await create(UserFactory)

        assert user.login_block() is None

    async def test_banned_user_is_blocked(self, create):
        user = await create(UserFactory)
        user.banned = datetime.now(timezone.utc)

        assert user.login_block() == "banned"

    async def test_future_suspension_blocks(self, create):
        user = await create(UserFactory)
        user.suspended_until = datetime.now(timezone.utc) + timedelta(days=1)

        assert user.login_block() == "suspended"

    async def test_past_suspension_does_not_block(self, create):
        user = await create(UserFactory)
        user.suspended_until = datetime.now(timezone.utc) - timedelta(seconds=1)

        assert user.login_block() is None

    async def test_ban_takes_precedence_over_suspension(self, create):
        user = await create(UserFactory)
        user.banned = datetime.now(timezone.utc)
        user.suspended_until = datetime.now(timezone.utc) + timedelta(days=1)

        assert user.login_block() == "banned"


class TestAvatar:
    async def test_without_avatar_meta_returns_default(self, create):
        user = await create(UserFactory)

        assert user.avatar == "avatar.png"

    async def test_with_avatar_meta_returns_user_specific_avatar(
        self, create, db_session
    ):
        user = await create(UserFactory)
        user.meta.append(UserMeta(key=UserMeta.MetaKeys.AVATAR_EXT.value, value="png"))
        await db_session.flush()

        assert user.avatar == f"{user.id}.png"


def _user() -> User:
    return User(username="perm-test", email="perm-test@example.com")


class TestGlobalPermissions:
    def test_unions_global_allows_across_roles_and_grants(self):
        user = _user()
        shared = RolePermission.ValidPermissions.ADMIN
        admins = Role(name="Admins", owner=user)
        admins.grant(shared)
        admins.grant(RolePermission.ValidPermissions.ACP_ACCESS)
        mods = Role(name="Moderators", owner=user)
        mods.grant(shared)
        mods.grant(RolePermission.ValidPermissions.ROLE_ADMIN)
        user.roles.extend([admins, mods])

        assert user.global_permissions == {"admin", "access_acp", "role_admin"}

    def test_global_deny_overrides_global_allow_from_another_role(self):
        user = _user()
        allow = RolePermission.ValidPermissions.ADMIN
        grants_role = Role(name="Admins", owner=user)
        grants_role.grant(allow)
        blocks_role = Role(name="Restricted", owner=user)
        blocks_role.grant(allow, effect=RolePermission.Effects.DENY)
        user.roles.extend([grants_role, blocks_role])

        assert user.global_permissions == set()

    def test_scoped_grant_is_ignored(self):
        user = _user()
        role = Role(name="PR Mods", owner=user)
        role.grant(
            RolePermission.ValidPermissions.FORUM_MODERATE,
            scope_type=RolePermission.ScopeTypes.FORUM,
            scope_id=5,
        )
        user.roles.append(role)

        assert user.global_permissions == set()

    def test_scoped_deny_does_not_suppress_global_allow_of_same_verb(self):
        user = _user()
        perm = RolePermission.ValidPermissions.FORUM_READ
        role = Role(name="Mixed", owner=user)
        role.grant(perm)
        role.grant(
            perm,
            scope_type=RolePermission.ScopeTypes.FORUM,
            scope_id=5,
            effect=RolePermission.Effects.DENY,
        )
        user.roles.append(role)

        assert user.global_permissions == {"forum_read"}

    def test_unions_assigned_and_implicit_roles(self):
        user = _user()
        assigned = Role(name="Moderators", owner=user)
        assigned.grant(RolePermission.ValidPermissions.ROLE_ADMIN)
        user.roles.append(assigned)
        registered = Role(name="Registered", owner=user)
        registered.grant(RolePermission.ValidPermissions.ACP_ACCESS)
        user.implicit_roles = (registered,)

        assert user.global_permissions == {"role_admin", "access_acp"}
