import pytest
from sqlalchemy import select, text

from app.exceptions import NotFoundException
from app.models import Deck, DeckPermission
from app.repositories import DeckRepository, GameRepository
from tests.factories import (
    ActivatedUserFactory,
    DeckTypeFactory,
    ForumFactory,
    SystemFactory,
)


@pytest.fixture
async def games_root_forum(create, db_session):
    forum = await create(ForumFactory, id=2, heritage=[])
    # Forcing an explicit id bypasses the "forums_id_seq" sequence, so any
    # later auto-generated forum id in this test could collide with it.
    await db_session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
            "(SELECT MAX(id) FROM forums))"
        )
    )
    return forum


@pytest.fixture
async def gm(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def system(create):
    return await create(SystemFactory, id="dnd5e")


@pytest.fixture
async def deck_type(create):
    return await create(DeckTypeFactory, deck_size=52)


@pytest.fixture
async def game(db_session, games_root_forum, gm, system):
    game_repository = GameRepository(db_session, principal=gm)
    return await game_repository.create(
        "My Campaign",
        system.id,
        [],
        gm.id,
        "3/w",
        4,
        1,
        None,
        None,
        True,
        None,
        None,
    )


@pytest.fixture
def repository(db_session, gm, wrap_in_savepoint):
    return DeckRepository(db_session, principal=gm)


@pytest.fixture
async def deck(repository, game, deck_type):
    return await repository.create(
        game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
    )


class TestCreate:
    async def test_create_deck_type_not_found_raises(self, repository, game):
        with pytest.raises(NotFoundException):
            await repository.create(
                game_id=game.id,
                label="Fate Deck",
                type="does-not-exist",
                permissions=[],
            )

    async def test_create_sets_deck_fields(self, repository, game, deck_type):
        deck = await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

        assert deck.id is not None
        assert deck.game_id == game.id
        assert deck.label == "Fate Deck"
        assert deck.type_id == deck_type.short
        assert deck.position == 0
        assert set(deck.order) == set(range(deck_type.deck_size))

    async def test_create_grants_permissions_to_listed_users(
        self, repository, db_session, game, deck_type, create
    ):
        player_a = await create(ActivatedUserFactory)
        player_b = await create(ActivatedUserFactory)

        deck = await repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[player_a.id, player_b.id],
        )

        permissions = await db_session.scalars(
            select(DeckPermission).where(DeckPermission.deck_id == deck.id)
        )
        assert {p.user_id for p in permissions} == {player_a.id, player_b.id}

    async def test_create_duplicate_permission_ids_deduplicated(
        self, repository, db_session, game, deck_type, create
    ):
        player = await create(ActivatedUserFactory)

        deck = await repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[player.id, player.id],
        )

        permissions = await db_session.scalars(
            select(DeckPermission).where(DeckPermission.deck_id == deck.id)
        )
        assert [p.user_id for p in permissions] == [player.id]


class TestGetById:
    async def test_get_by_id_loads_permissions(
        self, repository, db_session, game, deck_type, create
    ):
        player_a = await create(ActivatedUserFactory)
        player_b = await create(ActivatedUserFactory)
        created = await repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[player_a.id, player_b.id],
        )
        await db_session.flush()
        created_id, player_ids = created.id, {player_a.id, player_b.id}
        # Drop the identity-mapped instances so get_by_id must load permissions.
        db_session.expunge_all()

        deck = await repository.get_by_id(created_id)

        assert deck is not None
        assert deck.id == created_id
        assert deck.label == "Fate Deck"
        assert {p.user_id for p in deck.permissions} == player_ids


class TestGetAllForGame:
    async def test_get_all_for_game_loads_permissions_and_excludes_other_games(
        self, repository, db_session, gm, game, system, deck_type, create
    ):
        player = await create(ActivatedUserFactory)
        created = await repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[player.id],
        )
        other_game = await GameRepository(db_session, principal=gm).create(
            "Other Campaign",
            system.id,
            [],
            gm.id,
            "3/w",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )
        await repository.create(
            game_id=other_game.id,
            label="Other Deck",
            type=deck_type.short,
            permissions=[],
        )

        await db_session.flush()
        game_id, created_id, player_id = game.id, created.id, player.id
        # Drop the identity-mapped instances so the query must load permissions.
        db_session.expunge_all()

        decks = list(await repository.get_all_for_game(game_id))

        assert [d.id for d in decks] == [created_id]
        assert [p.user_id for p in decks[0].permissions] == [player_id]


class TestUpdate:
    async def test_update_type_not_found_raises(self, repository, deck):
        with pytest.raises(NotFoundException):
            await repository.update(
                deck, label="Fate Deck", type="does-not-exist", permissions=[]
            )

    async def test_update_same_type_does_not_reshuffle(
        self, repository, deck, deck_type
    ):
        original_order = list(deck.order)
        original_shuffled_at = deck.last_shuffled
        original_position = deck.position

        updated = await repository.update(
            deck, label="Renamed Deck", type=deck_type.short, permissions=[]
        )

        assert updated.label == "Renamed Deck"
        assert updated.order == original_order
        assert updated.last_shuffled == original_shuffled_at
        assert updated.position == original_position

    async def test_update_changing_type_reshuffles_and_resets_position(
        self, repository, deck, create
    ):
        new_type = await create(DeckTypeFactory, deck_size=20)

        updated = await repository.update(
            deck, label=deck.label, type=new_type.short, permissions=[]
        )

        assert updated.type_id == new_type.short
        assert set(updated.order) == set(range(new_type.deck_size))
        assert updated.position == 0

    async def test_update_replaces_permissions(
        self, repository, db_session, deck, deck_type, create
    ):
        old_player = await create(ActivatedUserFactory)
        new_player = await create(ActivatedUserFactory)
        await repository.update(
            deck, label=deck.label, type=deck_type.short, permissions=[old_player.id]
        )

        updated = await repository.update(
            deck, label=deck.label, type=deck_type.short, permissions=[new_player.id]
        )

        permissions = await db_session.scalars(
            select(DeckPermission).where(DeckPermission.deck_id == updated.id)
        )
        assert {p.user_id for p in permissions} == {new_player.id}

    async def test_update_duplicate_permission_ids_deduplicated(
        self, repository, db_session, deck, deck_type, create
    ):
        player = await create(ActivatedUserFactory)

        updated = await repository.update(
            deck,
            label=deck.label,
            type=deck_type.short,
            permissions=[player.id, player.id],
        )

        permissions = await db_session.scalars(
            select(DeckPermission).where(DeckPermission.deck_id == updated.id)
        )
        assert [p.user_id for p in permissions] == [player.id]


class TestShuffle:
    async def test_shuffle_deck_not_found_raises(self, repository):
        with pytest.raises(NotFoundException):
            await repository.shuffle(999999)

    async def test_shuffle_keeps_same_full_range(
        self, repository, db_session, deck, deck_type
    ):
        original_shuffled_at = deck.last_shuffled
        deck.position = 5
        await db_session.flush()

        await repository.shuffle(deck.id)

        await db_session.refresh(deck)
        assert set(deck.order) == set(range(deck_type.deck_size))
        assert deck.last_shuffled > original_shuffled_at
        assert deck.position == 0


class TestDelete:
    async def test_delete_removes_deck(self, repository, db_session, deck):
        await repository.delete(deck.id)

        assert await db_session.get(Deck, deck.id) is None

    async def test_delete_removes_permissions(
        self, repository, db_session, deck, create
    ):
        player = await create(ActivatedUserFactory)
        await repository.update(
            deck, label=deck.label, type=deck.type_id, permissions=[player.id]
        )

        await repository.delete(deck.id)

        permissions = await db_session.scalars(
            select(DeckPermission).where(DeckPermission.deck_id == deck.id)
        )
        assert list(permissions) == []
