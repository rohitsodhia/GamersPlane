import pytest

from app.models import User, UserMeta
from app.users.exceptions import UserExists
from app.users.functions import (
    check_for_existing_user,
    get_avatar_path,
    register_user,
)
from tests.factories import UserFactory


class TestGetAvatarPath:
    def test_with_user_id_and_ext_returns_user_avatar(self):
        assert get_avatar_path(user_id=5, ext="png") == "/ucp/avatars/5.png"

    def test_without_user_id_returns_default_avatar(self):
        assert get_avatar_path(ext="png") == "/ucp/avatars/avatar.png"

    def test_without_ext_returns_default_avatar(self):
        assert get_avatar_path(user_id=5) == "/ucp/avatars/avatar.png"

    def test_without_either_returns_default_avatar(self):
        assert get_avatar_path() == "/ucp/avatars/avatar.png"


class TestCheckForExistingUser:
    async def test_no_conflict_returns_none(self, db_session, create):
        await create(UserFactory)

        errors = await check_for_existing_user(
            db_session, User(email="new@example.com", username="newuser")
        )

        assert errors is None

    async def test_email_taken_returns_email_taken_error(self, db_session, create):
        existing = await create(UserFactory)

        errors = await check_for_existing_user(
            db_session, User(email=existing.email, username="newuser")
        )

        assert [e.code for e in errors] == ["email_taken"]

    async def test_username_taken_returns_username_taken_error(
        self, db_session, create
    ):
        existing = await create(UserFactory)

        errors = await check_for_existing_user(
            db_session, User(email="new@example.com", username=existing.username)
        )

        assert [e.code for e in errors] == ["username_taken"]

    async def test_both_taken_returns_both_errors(self, db_session, create):
        existing = await create(UserFactory)

        errors = await check_for_existing_user(
            db_session, User(email=existing.email, username=existing.username)
        )

        assert [e.code for e in errors] == ["email_taken", "username_taken"]

    async def test_email_taken_by_one_user_username_by_another(
        self, db_session, create
    ):
        by_email = await create(UserFactory)
        by_username = await create(UserFactory)

        errors = await check_for_existing_user(
            db_session,
            User(email=by_email.email, username=by_username.username),
        )

        assert {e.code for e in errors} == {"email_taken", "username_taken"}


class TestRegisterUser:
    async def test_creates_user_with_hashed_password_and_default_meta(
        self, db_session
    ):
        user = await register_user(
            db_session,
            email="new@example.com",
            username="newuser",
            password="ValidPass1!",
        )

        assert user.email == "new@example.com"
        assert user.username == "newuser"
        assert user.check_pass("ValidPass1!")
        assert user.id is not None

        meta = {m.key: m.value for m in user.meta}
        assert meta == {
            UserMeta.MetaKeys.GM_MAIL.value: True,
            UserMeta.MetaKeys.NEW_GAME_MAIL.value: True,
            UserMeta.MetaKeys.PM_MAIL.value: True,
            UserMeta.MetaKeys.POST_SIDE.value: "l",
            UserMeta.MetaKeys.SHOW_AVATARS.value: True,
        }

    async def test_existing_user_raises_user_exists(self, db_session, create):
        existing = await create(UserFactory)

        with pytest.raises(UserExists) as exc_info:
            await register_user(
                db_session,
                email=existing.email,
                username="another",
                password="ValidPass1!",
            )

        assert [e.code for e in exc_info.value.errors] == ["email_taken"]
