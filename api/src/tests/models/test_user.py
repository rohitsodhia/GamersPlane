import bcrypt

from app.models import Role, RolePermission, User, UserMeta
from tests.factories import UserFactory


class TestValidatePassword:
    def test_too_short_returns_error(self):
        errors = User.validate_password("short1")

        assert [e.code for e in errors] == ["pass_too_short"]

    def test_long_enough_returns_no_errors(self):
        assert User.validate_password("LongEnough1") == []


class TestHashPassword:
    def test_returns_bcrypt_hash_not_plaintext(self):
        hashed = User.hash_password("ValidPass1!")

        assert hashed != "ValidPass1!"
        assert bcrypt.checkpw(b"ValidPass1!", hashed.encode("utf-8"))


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


class TestActivate:
    async def test_sets_activated_on(self, create):
        user = await create(UserFactory)
        assert user.activated_on is None

        user.activate()

        assert user.activated_on is not None


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
    def test_no_roles_returns_empty_set(self):
        assert _user().global_permissions == set()

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
        perm = RolePermission.ValidPermissions.FORUM_ACCESS
        role = Role(name="Mixed", owner=user)
        role.grant(perm)
        role.grant(
            perm,
            scope_type=RolePermission.ScopeTypes.FORUM,
            scope_id=5,
            effect=RolePermission.Effects.DENY,
        )
        user.roles.append(role)

        assert user.global_permissions == {"access_forum"}


class TestRoleGrant:
    def test_defaults_to_global_allow(self):
        role = Role(name="Admins", owner=_user())
        permission = RolePermission.ValidPermissions.ADMIN

        rp = role.grant(permission)

        assert rp in role.grants
        assert rp.permission is permission
        assert rp.scope_type is None
        assert rp.scope_id is None
        assert rp.effect is RolePermission.Effects.ALLOW

    def test_passes_scope_and_effect_through(self):
        role = Role(name="PR Mods", owner=_user())

        rp = role.grant(
            RolePermission.ValidPermissions.FORUM_MODERATE,
            scope_type=RolePermission.ScopeTypes.FORUM,
            scope_id=7,
            effect=RolePermission.Effects.DENY,
        )

        assert rp.scope_type is RolePermission.ScopeTypes.FORUM
        assert rp.scope_id == 7
        assert rp.effect is RolePermission.Effects.DENY
