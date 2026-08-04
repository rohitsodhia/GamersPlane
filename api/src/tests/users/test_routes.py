from tests.factories import ActivatedUserFactory


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
