import pytest

from app.models import Permission


class TestSetPermission:
    def test_admin_sets_literal_value(self):
        permission = Permission()

        permission.set_permission(Permission.ValidPermissions.ADMIN)

        assert permission.permission == "admin"

    def test_role_admin_formats_template_with_role_id(self):
        permission = Permission()

        permission.set_permission(Permission.ValidPermissions.ROLE_ADMIN, role_id=5)

        assert permission.permission == "role_admin_5"

    def test_non_valid_permission_type_raises_value_error(self):
        permission = Permission()

        with pytest.raises(ValueError):
            permission.set_permission("admin")
