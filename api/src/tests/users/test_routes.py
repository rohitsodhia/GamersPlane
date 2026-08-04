from tests.factories import UserFactory


class TestSearchUser:
    async def test_search_user_requires_auth(self, client):
        response = await client.get("/users/search", params={"username": "someone"})

        assert response.status_code == 403

    async def test_search_user_found(self, authed_client, create):
        client, _user = authed_client
        other = await create(UserFactory, username="findme")

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
