class TestRollDiceBasic:
    async def test_roll_dice_basic(self, client):
        response = await client.get(
            "/tools/dice", params={"system": "basic", "roll": "2d6+3"}
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["groups"]) == 1
        group = body["groups"][0]
        assert group["expression"] == "2d6+3"
        assert group["terms"][0]["count"] == 2
        assert len(group["terms"][0]["rolls"]) == 2
        assert "total" in group
        assert "total" in body

    async def test_roll_dice_basic_invalid_expression(self, client):
        response = await client.get(
            "/tools/dice", params={"system": "basic", "roll": "0d6"}
        )

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
