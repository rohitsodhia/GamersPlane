import pytest

from app.models import UserMeta
from app.repositories.user_repository import UserRepository
from tests.factories import UserFactory


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

        await repository.update_user_meta(
            user, {UserMeta.MetaKeys.PRONOUNS: "she/her"}
        )

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
