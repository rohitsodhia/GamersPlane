import pytest

from app.models import RolePermission

Verbs = RolePermission.ValidPermissions
Scopes = RolePermission.ScopeTypes


class TestScopeAllowed:
    @pytest.mark.parametrize("verb", [Verbs.ADMIN, Verbs.ACP_ACCESS])
    def test_global_only_verb_allows_global_and_rejects_every_scope(self, verb):
        assert verb.scope_allowed(None) is True
        assert verb.scope_allowed(Scopes.FORUM) is False
        assert verb.scope_allowed(Scopes.ROLE) is False

    def test_role_admin_only_allows_role_scope(self):
        assert Verbs.ROLE_ADMIN.scope_allowed(Scopes.ROLE) is True
        assert Verbs.ROLE_ADMIN.scope_allowed(None) is False
        assert Verbs.ROLE_ADMIN.scope_allowed(Scopes.FORUM) is False

    def test_forum_verbs_only_allow_forum_scope(self):
        for verb in (Verbs.FORUM_READ, Verbs.FORUM_WRITE, Verbs.FORUM_MODERATE):
            assert verb.scope_allowed(Scopes.FORUM) is True
            assert verb.scope_allowed(None) is False
            assert verb.scope_allowed(Scopes.ROLE) is False
