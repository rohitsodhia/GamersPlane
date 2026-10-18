import pytest
from sqlalchemy import select, text

from app.models import Forum, Player, Role, RolePermission, UserRole
from app.models.game import PostFrequency
from app.repositories import GameRepository, PlayerRepository
from tests.factories import ActivatedUserFactory, ForumFactory, SystemFactory
from tests.threads.test_search_routes import add_thread

Verbs = RolePermission.ValidPermissions


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
            {"summary": "A tale"},
            {"info": "roll for stats"},
            False,
            None,
            {"loot": "enabled"},
        )

        assert game.id is not None
        assert game.title == "My Campaign"
        assert game.system_id == system.id
        assert game.gm_id == gm.id
        assert game.post_frequency == PostFrequency(3, "w")
        assert game.num_players == 4
        assert game.chars_per_player == 1
        assert game.description == {"summary": "A tale"}
        assert game.char_gen_info == {"info": "roll for stats"}
        assert game.public is False
        assert game.recruitment_thread_id is None
        assert game.advanced_options == {"loot": "enabled"}
        assert game.allowed_char_sheets == []

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
        assert root_forum.game_id == game.id

    async def test_create_creates_game_roles_named_after_game_id(
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

        gm_role = await db_session.get(Role, game.gm_role_id)
        player_role = await db_session.get(Role, game.player_role_id)
        assert gm_role.name == f"GM Role - Game #{game.id}"
        assert player_role.name == f"Player Role - Game #{game.id}"
        for role in (gm_role, player_role):
            assert role.owner_id == gm.id
            assert role.game_role == game.id

    async def test_create_adds_gm_to_gm_role_only(
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

        role_ids = await db_session.scalars(
            select(UserRole.role_id).where(UserRole.user_id == gm.id)
        )
        assert set(role_ids) == {game.gm_role_id}

    async def test_create_attaches_gm_as_accepted_gm_player(
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

        players = list(
            await db_session.scalars(select(Player).where(Player.game_id == game.id))
        )
        assert [(p.user_id, p.is_gm, p.state) for p in players] == [
            (gm.id, True, Player.States.ACCEPTED)
        ]

    async def test_create_grants_game_roles_on_root_forum(
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

        rows = await db_session.execute(
            select(
                RolePermission.role_id,
                RolePermission.permission,
                RolePermission.scope_type,
                RolePermission.scope_id,
                RolePermission.effect,
            ).where(RolePermission.role_id.in_([game.gm_role_id, game.player_role_id]))
        )
        grants = {}
        for role_id, permission, scope_type, scope_id, effect in rows:
            assert (scope_type, scope_id) == (
                RolePermission.ScopeTypes.FORUM,
                game.root_forum_id,
            )
            assert effect == RolePermission.Effects.ALLOW
            grants.setdefault(role_id, set()).add(permission)
        assert grants == {
            game.gm_role_id: {Verbs.FORUM_MODERATE},
            game.player_role_id: {
                Verbs.FORUM_READ,
                Verbs.FORUM_WRITE,
                Verbs.FORUM_EDIT,
                Verbs.FORUM_CREATE_THREAD,
                Verbs.FORUM_DELETE,
                Verbs.FORUM_ADD_ROLLS,
                Verbs.FORUM_ADD_DRAWS,
            },
        }

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

    async def test_get_returns_game_with_gm_eager_loaded(
        self, repository, gm, system, db_session
    ):
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
        await db_session.flush()
        created_id, gm_username = created.id, gm.username
        # Drop the identity-mapped instances so get() must load from the database.
        db_session.expunge_all()

        game = await repository.get(created_id)

        assert game is not None
        assert game.id == created_id
        assert game.title == "My Campaign"
        # Accessing an unloaded relationship on an async session raises
        # MissingGreenlet, so this only passes if gm was eagerly loaded.
        assert game.gm.username == gm_username

    async def test_get_eager_loads_allowed_char_sheets(
        self, repository, gm, system, create, db_session
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
        await db_session.flush()
        created_id, sheet_id = created.id, sheet.id
        db_session.expunge_all()

        game = await repository.get(created_id)

        assert {s.id for s in game.allowed_char_sheets} == {sheet_id}

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

    async def test_update_title_renames_root_forum(
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

        await repository.update(game, title="New Title")

        root_forum = await db_session.get(Forum, game.root_forum_id)
        await db_session.refresh(root_forum)
        assert root_forum.title == "New Title"

    async def test_get_latest_excludes_games_with_a_player_row_in_any_state(
        self, repository, gm, system, create, db_session
    ):
        viewer = await create(ActivatedUserFactory)
        open_game = await repository.create(
            "Open", system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )
        for state in Player.States:
            game = await repository.create(
                state.name,
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
            await PlayerRepository(db_session, principal=gm).attach_player_to_game(
                game.id, viewer.id, state=state
            )

        games = await repository.get_latest(None, 10, exclude_user_id=viewer.id)

        assert [g.id for g in games] == [open_game.id]

    async def test_get_last_activity_takes_the_latest_post_across_subforums(
        self, repository, gm, system, create, db_session
    ):
        busy = await repository.create(
            "Busy", system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )
        quiet = await repository.create(
            "Quiet", system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )
        root = await db_session.get(Forum, busy.root_forum_id)
        subforum = await create(
            ForumFactory,
            parent_id=root.id,
            heritage=[*root.heritage, root.id],
            game_id=busy.id,
        )
        await add_thread(create, db_session, root, days=3)
        latest = await add_thread(create, db_session, subforum, days=1)
        await add_thread(create, db_session, subforum, days=2)

        activity = await repository.get_last_activity([busy.id, quiet.id])

        assert activity == {busy.id: latest.last_post_at}

    async def test_get_last_activity_ignores_deleted_threads(
        self, repository, gm, system, create, db_session
    ):
        game = await repository.create(
            "Game", system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )
        root = await db_session.get(Forum, game.root_forum_id)
        live = await add_thread(create, db_session, root, days=3)
        deleted = await add_thread(create, db_session, root, days=1)
        deleted.deleted = deleted.last_post_at
        await db_session.flush()

        activity = await repository.get_last_activity([game.id])

        assert activity == {game.id: live.last_post_at}
