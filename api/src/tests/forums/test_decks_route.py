import pytest

from app.models import RolePermission
from app.repositories import DeckRepository
from tests.factories import ActivatedUserFactory, ForumFactory
from tests.game_forum import (
    PLAYER_VERBS,
    allow_drawing,
    make_game_forum,
    make_user_with,
)

Verbs = RolePermission.ValidPermissions


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


class TestGetForumDecks:
    async def test_gm_sees_every_deck_with_remaining(
        self, auth_as, create, db_session, world
    ):
        second = await DeckRepository(db_session, principal=world.gm).create(
            game_id=world.game.id,
            label="Second",
            type=world.deck.type_id,
            permissions=[],
        )
        await DeckRepository(db_session, principal=world.gm).draw(second, 5)
        client = auth_as(world.gm)

        response = await client.get(f"/forums/{world.forum.id}/decks")

        assert response.status_code == 200
        decks = {deck["id"]: deck for deck in response.json()["decks"]}
        assert set(decks) == {world.deck.id, second.id}
        assert decks[world.deck.id]["label"] == "Fate Deck"
        assert decks[world.deck.id]["type"] == world.deck.type_id
        assert decks[world.deck.id]["remaining"] == 52
        assert decks[second.id]["remaining"] == 47

    async def test_player_sees_only_permitted_decks(
        self, auth_as, create, db_session, world
    ):
        await DeckRepository(db_session, principal=world.gm).create(
            game_id=world.game.id,
            label="Hidden",
            type=world.deck.type_id,
            permissions=[],
        )
        player = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        await allow_drawing(db_session, player, world.deck)
        await DeckRepository(db_session, principal=world.gm).draw(world.deck, 3)
        client = auth_as(player)

        response = await client.get(f"/forums/{world.forum.id}/decks")

        assert response.status_code == 200
        decks = response.json()["decks"]
        assert [deck["id"] for deck in decks] == [world.deck.id]
        assert decks[0]["remaining"] == 49

    async def test_non_game_forum_has_no_decks(self, auth_as, create, db_session):
        forum = await create(ForumFactory, heritage=[])
        user = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        client = auth_as(user)

        response = await client.get(f"/forums/{forum.id}/decks")

        assert response.status_code == 200
        assert response.json() == {"decks": []}

    async def test_without_add_draws_has_no_decks(
        self, auth_as, create, db_session, world
    ):
        verbs = [verb for verb in PLAYER_VERBS if verb != Verbs.FORUM_ADD_DRAWS]
        player = await make_user_with(create, db_session, world.forum, *verbs)
        await allow_drawing(db_session, player, world.deck)
        client = auth_as(player)

        response = await client.get(f"/forums/{world.forum.id}/decks")

        assert response.status_code == 200
        assert response.json() == {"decks": []}

    async def test_moderator_without_gm_or_permission_sees_none(
        self, auth_as, create, db_session, world
    ):
        # forum_moderate implies add_draws, but deck access still applies.
        moderator = await make_user_with(
            create, db_session, world.forum, Verbs.FORUM_MODERATE
        )
        client = auth_as(moderator)

        response = await client.get(f"/forums/{world.forum.id}/decks")

        assert response.status_code == 200
        assert response.json() == {"decks": []}

    async def test_unreadable_forum_is_not_found(self, auth_as, create, open_forums):
        forum = await create(ForumFactory, heritage=[])
        await open_forums()
        client = auth_as(await create(ActivatedUserFactory))

        response = await client.get(f"/forums/{forum.id}/decks")

        assert response.status_code == 404

    async def test_missing_forum_is_not_found(self, auth_as, create):
        client = auth_as(await create(ActivatedUserFactory))

        response = await client.get("/forums/999999/decks")

        assert response.status_code == 404
