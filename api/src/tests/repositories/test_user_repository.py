from datetime import datetime, timedelta, timezone

import pytest

from app.models import UserMeta
from app.repositories.user_repository import UserRepository
from tests.factories import ActivatedUserFactory, UserFactory


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

    async def test_get_user_not_found(self, repository):
        found = await repository.get_user(999999)

        assert found is None

    async def test_get_user_by_email(self, repository, create):
        user = await create(UserFactory, email="findme@example.com")

        found = await repository.get_user_by_email("findme@example.com")

        assert found is not None
        assert found.id == user.id

    async def test_get_user_by_email_not_found(self, repository):
        found = await repository.get_user_by_email("nobody@example.com")

        assert found is None

    async def test_get_user_by_username(self, repository, create):
        user = await create(ActivatedUserFactory, username="findme")

        found = await repository.get_user_by_username("findme")

        assert found is not None
        assert found.id == user.id

    async def test_get_user_by_username_not_found(self, repository):
        found = await repository.get_user_by_username("nobody")

        assert found is None

    async def test_get_user_by_username_is_exact_not_partial(self, repository, create):
        await create(ActivatedUserFactory, username="findme")

        found = await repository.get_user_by_username("findm")

        assert found is None

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

    async def test_get_user_by_id_not_found(self, repository):
        found = await repository.get_user_by_id(999999)

        assert found is None

    async def test_get_user_by_id_excludes_unactivated(self, repository, create):
        user = await create(UserFactory)

        found = await repository.get_user_by_id(user.id)

        assert found is None

    async def test_get_user_by_id_include_meta_loads_meta(self, repository, create):
        user = await create(ActivatedUserFactory)
        await repository.update_user_meta(
            user, {UserMeta.MetaKeys.PRONOUNS: "they/them"}
        )

        found = await repository.get_user_by_id(user.id, include_meta=True)

        assert found is not None
        meta = {m.key: m.value for m in found.meta}
        assert meta == {UserMeta.MetaKeys.PRONOUNS.value: "they/them"}

    async def test_get_user_by_id_include_meta_empty_when_no_meta(
        self, repository, create
    ):
        user = await create(ActivatedUserFactory)

        found = await repository.get_user_by_id(user.id, include_meta=True)

        assert found is not None
        assert found.meta == []

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

    async def test_update_user_meta_casts_bool(self, repository, create):
        user = await create(UserFactory)

        await repository.update_user_meta(user, {UserMeta.MetaKeys.GM_MAIL: True})

        assert user.meta[0].value is True

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
