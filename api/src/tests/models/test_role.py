from app.models import Role, RolePermission, User


class TestName:
    def test_setting_and_changing_name_recomputes_plural(self):
        role = Role(name="Moderator")

        assert role.name == "Moderator"
        assert role.plural == "Moderators"

        role.name = "Admin"

        assert role.name == "Admin"
        assert role.plural == "Admins"


class TestGrant:
    def test_defaults_to_global_allow(self):
        owner = User(username="perm-test", email="perm-test@example.com")
        role = Role(name="Admins", owner=owner)
        permission = RolePermission.ValidPermissions.ADMIN

        rp = role.grant(permission)

        assert rp in role.grants
        assert rp.permission is permission
        assert rp.scope_type is None
        assert rp.scope_id is None
        assert rp.effect is RolePermission.Effects.ALLOW
