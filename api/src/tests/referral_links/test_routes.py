from tests.factories import ReferralLinkFactory


class TestGetReferralLinks:
    async def test_get_referral_links_is_public(self, client):
        response = await client.get("/referral_links/")

        assert response.status_code == 200

    async def test_get_referral_links(self, client, create):
        await create(
            ReferralLinkFactory, title="Amazon", link="https://amazon.com", order=1
        )

        response = await client.get("/referral_links/")

        assert response.status_code == 200
        body = response.json()
        assert body["referralLinks"] == [
            {
                "key": body["referralLinks"][0]["key"],
                "title": "Amazon",
                "link": "https://amazon.com/",
                "order": 1,
            }
        ]

    async def test_get_referral_links_empty(self, client):
        response = await client.get("/referral_links/")

        assert response.status_code == 200
        assert response.json()["referralLinks"] == []
