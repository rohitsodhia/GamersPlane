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
            text("SELECT setval(pg_get_serial_sequence('forums', 'id'), "
                 "(SELECT MAX(id) FROM forums))")
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
            "My Campaign", system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )

        assert game.allowed_char_sheets == []

    async def test_create_creates_root_forum_under_games_root(
        self, repository, gm, system, games_root_forum, db_session
    ):
        game = await repository.create(
            "My Campaign", system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )

        root_forum = await db_session.get(Forum, game.root_forum_id)
        assert root_forum.title == "My Campaign"
        assert root_forum.parent_id == games_root_forum.id

    async def test_create_creates_player_role_named_after_game_id(
        self, repository, gm, system, db_session
    ):
        game = await repository.create(
            "My Campaign", system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )

        role = await db_session.get(Role, game.role_id)
        assert role.name == f"Game Id {game.id} Player"
        assert role.owner_id == gm.id
