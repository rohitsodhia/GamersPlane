import pytest


class TestForumSubType:
    async def test_missing_row_reads_as_new_content(self, authed_client):
        client, _user = authed_client

        response = await client.get("/me?full=true")

        assert response.json()["forumSubType"] == "new content"

    @pytest.mark.parametrize("value", ["all", "new content", "none"])
    async def test_round_trips(self, authed_client, value):
        client, _user = authed_client

        saved = await client.post("/me", json={"forumSubType": value})
        response = await client.get("/me?full=true")

        assert saved.json()["updated"]["forumSubType"] == value
        assert response.json()["forumSubType"] == value

    async def test_rejects_an_unknown_value(self, authed_client):
        client, _user = authed_client

        response = await client.post("/me", json={"forumSubType": "sometimes"})

        assert response.status_code == 422
