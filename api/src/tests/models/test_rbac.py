import pytest

from app.models import RolePermission

Verbs = RolePermission.ValidPermissions
Scopes = RolePermission.ScopeTypes


class TestScopeAllowed:
    @pytest.mark.parametrize(
        ("verb", "sole_allowed_scope"),
        [
            (Verbs.ADMIN, None),
            (Verbs.MANAGE_USERS, None),
            (Verbs.ROLE_ADMIN, Scopes.ROLE),
            (Verbs.FORUM_READ, Scopes.FORUM),
        ],
    )
    def test_verb_allows_only_its_own_scope(self, verb, sole_allowed_scope):
        for scope in (None, Scopes.FORUM, Scopes.ROLE):
            assert verb.scope_allowed(scope) is (scope == sole_allowed_scope)
