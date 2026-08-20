class TestRollDiceBasic:
    async def test_roll_dice_is_public(self, client):
        response = await client.get("/tools/dice", params={"system": "basic", "roll": "2d6"})

        assert response.status_code == 200

    async def test_roll_dice_basic(self, client):
        response = await client.get("/tools/dice", params={"system": "basic", "roll": "2d6+3"})

        assert response.status_code == 200
        body = response.json()
        assert len(body["groups"]) == 1
        group = body["groups"][0]
        assert group["expression"] == "2d6+3"
        assert group["modifier"] == 3
        term = group["terms"][0]
        assert term["count"] == 2
        assert term["sides"] == 6
        assert len(term["rolls"]) == 2
        assert all(1 <= r <= 6 for r in term["rolls"])
        assert group["total"] == term["subtotal"] + 3
        assert body["total"] == group["total"]

    async def test_roll_dice_basic_invalid_expression(self, client):
        response = await client.get("/tools/dice", params={"system": "basic", "roll": "0d6"})

        assert response.status_code == 400


class TestRollDiceFate:
    async def test_roll_dice_fate(self, client):
        response = await client.get(
            "/tools/dice", params={"system": "fate", "roll": "4", "modifier": 1}
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["rolls"]) == 4
        assert all(r in (-1, 0, 1) for r in body["rolls"])
        assert body["modifier"] == 1
        assert body["total"] == sum(body["rolls"]) + 1


class TestRollDiceFengShui:
    async def test_roll_dice_fengshui_standard(self, client):
        response = await client.get(
            "/tools/dice",
            params={"system": "fengshui", "roll": "5", "roll_type": "standard"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["action_value"] == 5
        assert body["extra"] is None
        assert body["total"] == 5 + sum(body["positive"]) - sum(body["negative"])

    async def test_roll_dice_fengshui_fortune_has_extra(self, client):
        response = await client.get(
            "/tools/dice",
            params={"system": "fengshui", "roll": "0", "roll_type": "fortune"},
        )

        assert response.status_code == 200
        assert response.json()["extra"] is not None


class TestRollDiceStarWarsFFG:
    async def test_roll_dice_starwarsffg(self, client):
        response = await client.get(
            "/tools/dice",
            params={"system": "starwarsffg", "roll": "ability,proficiency,boost"},
        )

        assert response.status_code == 200
        body = response.json()
        assert [r["die"] for r in body["rolls"]] == ["ability", "proficiency", "boost"]
        assert set(body["totals"].keys()) == {
            "success",
            "advantage",
            "triumph",
            "failure",
            "threat",
            "despair",
            "whiteDot",
            "blackDot",
        }


class TestRollDiceInvalidSystem:
    async def test_roll_dice_invalid_system(self, client):
        response = await client.get("/tools/dice", params={"system": "bogus", "roll": "1"})

        assert response.status_code == 422
