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


class TestCreate:
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
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
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

    @pytest.fixture
    async def game(self, db_session, gm, system):
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
    def repository(self, db_session, gm, wrap_in_savepoint):
        return DeckRepository(db_session, principal=gm)

    async def test_create_deck_type_not_found_raises(self, repository, game):
        with pytest.raises(NotFoundException):
            await repository.create(
                game_id=game.id,
                label="Fate Deck",
                type="does-not-exist",
                permissions=[],
            )

    async def test_create_sets_deck_fields(self, repository, db_session, game, deck_type):
        deck = await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

        assert deck.id is not None
        assert deck.game_id == game.id
        assert deck.label == "Fate Deck"
        assert deck.type_id == deck_type.short
        assert deck.position == 0

    async def test_create_order_is_a_shuffled_full_range(
        self, repository, game, deck_type
    ):
        deck = await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

        assert set(deck.order) == set(range(deck_type.deck_size))

    async def test_create_last_shuffled_is_timezone_aware(
        self, repository, game, deck_type
    ):
        deck = await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

        assert deck.last_shuffled.tzinfo is not None

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
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
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
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

    @pytest.fixture
    async def game(self, db_session, gm, system):
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
    def repository(self, db_session, gm, wrap_in_savepoint):
        return DeckRepository(db_session, principal=gm)

    async def test_get_by_id_returns_deck(self, repository, game, deck_type):
        created = await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

        deck = await repository.get_by_id(created.id)

        assert deck is not None
        assert deck.id == created.id
        assert deck.label == "Fate Deck"

    async def test_get_by_id_loads_permissions(
        self, repository, game, deck_type, create
    ):
        player_a = await create(ActivatedUserFactory)
        player_b = await create(ActivatedUserFactory)
        created = await repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[player_a.id, player_b.id],
        )

        deck = await repository.get_by_id(created.id)

        assert {p.user_id for p in deck.permissions} == {player_a.id, player_b.id}


class TestGetAllForGame:
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
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
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

    @pytest.fixture
    async def game(self, db_session, gm, system):
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
    def repository(self, db_session, gm, wrap_in_savepoint):
        return DeckRepository(db_session, principal=gm)

    async def test_get_all_for_game_returns_decks_for_game(
        self, repository, game, deck_type
    ):
        deck = await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

        decks = await repository.get_all_for_game(game.id)

        assert [d.id for d in decks] == [deck.id]

    async def test_get_all_for_game_excludes_other_games(
        self, repository, db_session, gm, game, system, deck_type
    ):
        game_repository = GameRepository(db_session, principal=gm)
        other_game = await game_repository.create(
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

        decks = await repository.get_all_for_game(game.id)

        assert list(decks) == []

    async def test_get_all_for_game_loads_permissions(
        self, repository, game, deck_type, create
    ):
        player = await create(ActivatedUserFactory)
        await repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[player.id],
        )

        decks = await repository.get_all_for_game(game.id)

        assert [p.user_id for p in list(decks)[0].permissions] == [player.id]


class TestUpdate:
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
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
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

    @pytest.fixture
    async def game(self, db_session, gm, system):
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
    def repository(self, db_session, gm, wrap_in_savepoint):
        return DeckRepository(db_session, principal=gm)

    @pytest.fixture
    async def deck(self, repository, game, deck_type):
        return await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

    async def test_update_type_not_found_raises(self, repository, deck):
        with pytest.raises(NotFoundException):
            await repository.update(
                deck, label="Fate Deck", type="does-not-exist", permissions=[]
            )

    async def test_update_changes_label(self, repository, deck, deck_type):
        updated = await repository.update(
            deck, label="Renamed Deck", type=deck_type.short, permissions=[]
        )

        assert updated.label == "Renamed Deck"

    async def test_update_same_type_does_not_reshuffle(self, repository, deck, deck_type):
        original_order = list(deck.order)
        original_shuffled_at = deck.last_shuffled
        original_position = deck.position

        updated = await repository.update(
            deck, label=deck.label, type=deck_type.short, permissions=[]
        )

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
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
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
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

    @pytest.fixture
    async def game(self, db_session, gm, system):
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
    def repository(self, db_session, gm, wrap_in_savepoint):
        return DeckRepository(db_session, principal=gm)

    @pytest.fixture
    async def deck(self, repository, game, deck_type):
        return await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

    async def test_shuffle_deck_not_found_raises(self, repository):
        with pytest.raises(NotFoundException):
            await repository.shuffle(999999)

    async def test_shuffle_keeps_same_full_range(
        self, repository, db_session, deck, deck_type
    ):
        await repository.shuffle(deck.id)

        await db_session.refresh(deck)
        assert set(deck.order) == set(range(deck_type.deck_size))

    async def test_shuffle_updates_last_shuffled(self, repository, db_session, deck):
        original_shuffled_at = deck.last_shuffled

        await repository.shuffle(deck.id)

        await db_session.refresh(deck)
        assert deck.last_shuffled > original_shuffled_at

    async def test_shuffle_resets_position_to_zero(self, repository, db_session, deck):
        deck.position = 5
        await db_session.flush()

        await repository.shuffle(deck.id)

        await db_session.refresh(deck)
        assert deck.position == 0


class TestDelete:
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
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
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

    @pytest.fixture
    async def game(self, db_session, gm, system):
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
    def repository(self, db_session, gm, wrap_in_savepoint):
        return DeckRepository(db_session, principal=gm)

    @pytest.fixture
    async def deck(self, repository, game, deck_type):
        return await repository.create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )

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

    async def test_delete_missing_deck_is_a_no_op(self, repository):
        await repository.delete(999999)


class TestGetDeckTypes:
    @pytest.fixture
    def repository(self, db_session, wrap_in_savepoint):
        return DeckRepository(db_session, principal=None)

    async def test_get_deck_types_returns_all_types(self, repository, create):
        type_a = await create(DeckTypeFactory)
        type_b = await create(DeckTypeFactory)

        deck_types = await repository.get_deck_types()

        assert {dt.short for dt in deck_types} == {type_a.short, type_b.short}
