from app.models import Role


class TestName:
    def test_setting_name_updates_plural(self):
        role = Role(name="Moderator")

        assert role.name == "Moderator"
        assert role.plural == "Moderators"

    def test_changing_name_recomputes_plural(self):
        role = Role(name="Moderator")

        role.name = "Admin"

        assert role.name == "Admin"
        assert role.plural == "Admins"
