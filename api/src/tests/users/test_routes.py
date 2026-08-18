from datetime import date

from app.models import UserMeta
from app.repositories.user_repository import UserRepository
from tests.factories import ActivatedUserFactory, PostFactory, ThreadFactory


class TestSearchUser:
    async def test_search_user_requires_auth(self, client):
        response = await client.get("/users/search", params={"username": "someone"})

        assert response.status_code == 403

    async def test_search_user_found(self, authed_client, create):
        client, _user = authed_client
        other = await create(ActivatedUserFactory, username="findme")

        response = await client.get("/users/search", params={"username": "findme"})

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == other.id
        assert body["user"]["username"] == other.username

    async def test_search_user_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.get("/users/search", params={"username": "nobody"})

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "user_not_found"


class TestGetUser:
    async def test_get_user_found(self, client, create):
        user = await create(ActivatedUserFactory)

        response = await client.get(f"/users/{user.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == user.id
        assert body["user"]["username"] == user.username

    async def test_get_user_not_found(self, client):
        response = await client.get("/users/999999")

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "user_not_found"

    async def test_get_user_defaults_when_no_meta_or_posts(self, client, create):
        user = await create(ActivatedUserFactory)

        response = await client.get(f"/users/{user.id}")

        assert response.status_code == 200
        body = response.json()["user"]
        assert body["avatar"] == user.avatar_url
        assert body["pronouns"] is None
        assert body["location"] is None
        assert body["showAge"] is False
        assert body["age"] is None
        assert body["postCount"] == 0
        assert body["communityPostCount"] == 0
        assert body["gamePostCount"] == 0

    async def test_get_user_includes_meta_fields(self, client, create, db_session):
        user = await create(ActivatedUserFactory)
        user_repository = UserRepository(db_session)
        await user_repository.update_user_meta(
            user,
            {
                UserMeta.MetaKeys.PRONOUNS: "they/them",
                UserMeta.MetaKeys.LOCATION: "Toronto",
                UserMeta.MetaKeys.BIRTHDAY: date(1990, 1, 1),
                UserMeta.MetaKeys.SHOW_AGE: True,
            },
        )

        response = await client.get(f"/users/{user.id}")

        body = response.json()["user"]
        assert body["pronouns"] == "they/them"
        assert body["location"] == "Toronto"
        assert body["showAge"] is True
        assert body["age"] is not None

    async def test_get_user_age_hidden_when_show_age_false(
        self, client, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        user_repository = UserRepository(db_session)
        await user_repository.update_user_meta(
            user,
            {
                UserMeta.MetaKeys.BIRTHDAY: date(1990, 1, 1),
                UserMeta.MetaKeys.SHOW_AGE: False,
            },
        )

        response = await client.get(f"/users/{user.id}")

        body = response.json()["user"]
        assert body["showAge"] is False
        assert body["age"] is None

    async def test_get_user_reflects_post_counts(self, client, create):
        user = await create(ActivatedUserFactory)
        thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread, author=user)

        response = await client.get(f"/users/{user.id}")

        body = response.json()["user"]
        assert body["postCount"] == 1
        assert body["communityPostCount"] == 1
        assert body["gamePostCount"] == 0
