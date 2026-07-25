import bcrypt

from app.models import Permission, Role, User, UserMeta
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
        user.meta.append(
            UserMeta(key=UserMeta.MetaKeys.AVATAR_EXT.value, value="png")
        )
        await db_session.flush()

        assert user.avatar == f"{user.id}.png"


class TestPermissions:
    async def test_no_roles_returns_empty_list(self, create):
        user = await create(UserFactory)

        assert user.permissions == []

    async def test_aggregates_permissions_across_roles(
        self, create, db_session, wrap_in_savepoint
    ):
        user = await create(UserFactory)
        role = Role(name="Admins", owner=user)
        permission = Permission(permission="admin")
        role.permissions.append(permission)
        user.roles.append(role)
        db_session.add_all([role, permission])
        await db_session.flush()

        assert user.permissions == ["admin"]

    async def test_dedupes_permissions_shared_across_roles(
        self, create, db_session, wrap_in_savepoint
    ):
        user = await create(UserFactory)
        shared = Permission(permission="admin")
        role_a = Role(name="Admins", owner=user)
        role_b = Role(name="Moderators", owner=user)
        role_a.permissions.append(shared)
        role_b.permissions.append(shared)
        user.roles.extend([role_a, role_b])
        db_session.add_all([role_a, role_b, shared])
        await db_session.flush()

        assert user.permissions == ["admin"]
