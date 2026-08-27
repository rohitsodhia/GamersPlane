import pytest
from sqlalchemy import text

from app.models import Forum, Role
from app.models.game import PostFrequency
from app.repositories import GameRepository
from tests.factories import ActivatedUserFactory, ForumFactory, SystemFactory


class TestGameRepository:
    @pytest.fixture
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

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
    async def repository(self, db_session, gm, wrap_in_savepoint):
        return GameRepository(db_session, principal=gm)

    async def test_create_sets_basic_fields(self, repository, gm, system):
        game = await repository.create(
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

        assert game.id is not None
        assert game.title == "My Campaign"
        assert game.system_id == system.id
        assert game.gm_id == gm.id
        assert game.post_frequency == PostFrequency(3, "w")
        assert game.num_players == 4
        assert game.chars_per_player == 1
        assert game.description is None
        assert game.char_gen_info is None
        assert game.public is True
        assert game.recruitment_thread_id is None
        assert game.advanced_options is None

    async def test_create_sets_description_and_char_gen_info(
        self, repository, gm, system
    ):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            {"summary": "A tale"},
            {"info": "roll for stats"},
            False,
            None,
            {"loot": "enabled"},
        )

        assert game.description == {"summary": "A tale"}
        assert game.char_gen_info == {"info": "roll for stats"}
        assert game.public is False
        assert game.advanced_options == {"loot": "enabled"}

    async def test_create_attaches_allowed_char_sheets(
        self, repository, gm, system, create
    ):
        sheet_a = await create(SystemFactory, id="sheet-a")
        sheet_b = await create(SystemFactory, id="sheet-b")

        game = await repository.create(
            "My Campaign",
            system.id,
            [sheet_a.id, sheet_b.id],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        assert {s.id for s in game.allowed_char_sheets} == {sheet_a.id, sheet_b.id}

    async def test_create_with_no_allowed_char_sheets(self, repository, gm, system):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        assert game.allowed_char_sheets == []

    async def test_create_creates_root_forum_under_games_root(
        self, repository, gm, system, games_root_forum, db_session
    ):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        root_forum = await db_session.get(Forum, game.root_forum_id)
        assert root_forum.title == "My Campaign"
        assert root_forum.parent_id == games_root_forum.id

    async def test_create_creates_player_role_named_after_game_id(
        self, repository, gm, system, db_session
    ):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        role = await db_session.get(Role, game.role_id)
        assert role.name == f"Game Id {game.id} Player"
        assert role.owner_id == gm.id

    async def test_get_returns_the_game(self, repository, gm, system):
        created = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        game = await repository.get(created.id)

        assert game is not None
        assert game.id == created.id
        assert game.title == "My Campaign"

    async def test_get_returns_none_for_missing_id(self, repository):
        game = await repository.get(999999)

        assert game is None

    async def test_exists_returns_true_for_existing_game(self, repository, gm, system):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        assert await repository.exists(game.id) is True

    async def test_exists_returns_false_for_missing_id(self, repository):
        assert await repository.exists(999999) is False

    async def test_exists_returns_false_for_soft_deleted_game(
        self, repository, gm, system, db_session
    ):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )
        game.deleted = game.created
        db_session.add(game)
        await db_session.flush()

        assert await repository.exists(game.id) is False

    async def test_get_eager_loads_gm(self, repository, gm, system):
        created = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        game = await repository.get(created.id)

        # Accessing an unloaded relationship on an async session raises
        # MissingGreenlet, so this only passes if gm was eagerly loaded.
        assert game.gm.username == gm.username

    async def test_get_eager_loads_allowed_char_sheets(
        self, repository, gm, system, create
    ):
        sheet = await create(SystemFactory, id="sheet-a")
        created = await repository.create(
            "My Campaign",
            system.id,
            [sheet.id],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        game = await repository.get(created.id)

        assert {s.id for s in game.allowed_char_sheets} == {sheet.id}

    async def test_update_sets_single_field(self, repository, gm, system):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        updated = await repository.update(game, public=False)

        assert updated.public is False

    async def test_update_sets_multiple_fields(self, repository, gm, system):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        updated = await repository.update(game, public=False, title="New Title")

        assert updated.public is False
        assert updated.title == "New Title"

    async def test_update_persists_changes(self, repository, gm, system, db_session):
        game = await repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        await repository.update(game, public=False)

        refetched = await repository.get(game.id)
        assert refetched.public is False
