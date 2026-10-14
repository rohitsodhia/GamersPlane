from datetime import datetime, timedelta, timezone

import pytest

from app.models import UserMeta, UserRole
from app.repositories.user_repository import UserRepository
from tests.factories import ActivatedUserFactory, RoleFactory, UserFactory


class TestUserRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return UserRepository(db_session)

    async def test_get_user(self, repository, create):
        user = await create(UserFactory)

        found = await repository.get_user(user.id)

        assert found is not None
        assert found.id == user.id
        assert found.email == user.email

    async def test_get_role_members_sorted_and_only_that_role(
        self, repository, db_session, create
    ):
        role = RoleFactory.build()
        other_role = RoleFactory.build()
        db_session.add_all([role, other_role])
        bob = await create(ActivatedUserFactory, username="bob")
        alice = await create(ActivatedUserFactory, username="Alice")
        carol = await create(ActivatedUserFactory, username="carol")
        outsider = await create(ActivatedUserFactory, username="aaa")
        await db_session.flush()
        db_session.add_all(
            [
                UserRole(user_id=carol.id, role_id=role.id),
                UserRole(user_id=bob.id, role_id=role.id),
                UserRole(user_id=alice.id, role_id=role.id),
                UserRole(user_id=outsider.id, role_id=other_role.id),
            ]
        )
        await db_session.flush()

        members = await repository.get_role_members(role.id)

        assert [user.username for user in members] == ["Alice", "bob", "carol"]

    async def test_get_role_members_excludes_banned_unactivated_and_deleted_role(
        self, repository, db_session, create
    ):
        role = RoleFactory.build()
        dead_role = RoleFactory.build(deleted=datetime.now(timezone.utc))
        db_session.add_all([role, dead_role])
        good = await create(ActivatedUserFactory, username="good")
        banned = await create(ActivatedUserFactory, username="banned")
        banned.banned = datetime.now(timezone.utc)
        pending = await create(UserFactory, username="pending")
        await db_session.flush()
        db_session.add_all(
            [
                UserRole(user_id=good.id, role_id=role.id),
                UserRole(user_id=banned.id, role_id=role.id),
                UserRole(user_id=pending.id, role_id=role.id),
                UserRole(user_id=good.id, role_id=dead_role.id),
            ]
        )
        await db_session.flush()

        assert [u.username for u in await repository.get_role_members(role.id)] == [
            "good"
        ]
        assert await repository.get_role_members(dead_role.id) == []

    async def test_get_user_by_email(self, repository, create):
        user = await create(UserFactory, email="findme@example.com")

        found = await repository.get_user_by_email("findme@example.com")

        assert found is not None
        assert found.id == user.id

    async def test_get_user_by_username_is_case_insensitive(self, repository, create):
        user = await create(ActivatedUserFactory, username="FindMe")

        found = await repository.get_user_by_username("findme")

        assert found is not None
        assert found.id == user.id

    async def test_get_user_by_username_excludes_unactivated(self, repository, create):
        await create(UserFactory, username="findme")

        found = await repository.get_user_by_username("findme")

        assert found is None

    async def test_get_user_by_id(self, repository, create):
        user = await create(ActivatedUserFactory)

        found = await repository.get_user_by_id(user.id)

        assert found is not None
        assert found.id == user.id

        unactivated = await create(UserFactory)
        assert await repository.get_user_by_id(unactivated.id) is None

    async def test_get_user_by_id_include_meta_loads_meta(self, repository, create):
        user = await create(ActivatedUserFactory)
        await repository.update_user_meta(
            user, {UserMeta.MetaKeys.PRONOUNS: "they/them"}
        )

        found = await repository.get_user_by_id(user.id, include_meta=True)

        assert found is not None
        meta = {m.key: m.value for m in found.meta}
        assert meta == {UserMeta.MetaKeys.PRONOUNS.value: "they/them"}

    async def test_update_user_meta_creates_new(self, repository, create):
        user = await create(UserFactory)

        await repository.update_user_meta(
            user, {UserMeta.MetaKeys.PRONOUNS: "they/them"}
        )

        assert len(user.meta) == 1
        assert user.meta[0].key == UserMeta.MetaKeys.PRONOUNS.value
        assert user.meta[0].value == "they/them"

    async def test_update_user_meta_updates_existing(self, repository, create):
        user = await create(UserFactory)
        await repository.update_user_meta(
            user, {UserMeta.MetaKeys.PRONOUNS: "they/them"}
        )

        await repository.update_user_meta(user, {UserMeta.MetaKeys.PRONOUNS: "she/her"})

        assert len(user.meta) == 1
        assert user.meta[0].value == "she/her"

    async def test_delete_user_meta(self, repository, create):
        user = await create(UserFactory)
        await repository.update_user_meta(
            user, {UserMeta.MetaKeys.PRONOUNS: "they/them"}
        )

        await repository.delete_user_meta(user, UserMeta.MetaKeys.PRONOUNS)

        assert user.meta == []

    async def test_delete_user_meta_missing_key_is_noop(self, repository, create):
        user = await create(UserFactory)

        await repository.delete_user_meta(user, UserMeta.MetaKeys.PRONOUNS)

        assert user.meta == []

    async def test_update_last_activity_sets_when_never_set(self, repository, create):
        user = await create(UserFactory)
        assert user.last_activity is None

        await repository.update_last_activity(user)

        assert user.last_activity is not None

    async def test_update_last_activity_updates_when_stale(self, repository, create):
        user = await create(UserFactory)
        stale = datetime.now(timezone.utc) - timedelta(minutes=10)
        user.last_activity = stale

        await repository.update_last_activity(user)

        assert user.last_activity > stale

    async def test_update_last_activity_skips_when_recent(self, repository, create):
        user = await create(UserFactory)
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        user.last_activity = recent

        await repository.update_last_activity(user)

        assert user.last_activity == recent
