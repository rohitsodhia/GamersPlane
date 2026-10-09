from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from app.models import Player, UserRole
from app.repositories import GameRepository
from app.repositories.player_repository import DuplicatePlayerError, PlayerRepository
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    RoleFactory,
    SystemFactory,
)


async def role_ids_of(db_session, user_id):
    """Ids of the roles the user holds (soft-deleted memberships excluded)."""
    rows = await db_session.scalars(
        select(UserRole.role_id).where(UserRole.user_id == user_id)
    )
    return set(rows)


class TestPlayerRepository:
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
    async def game(self, db_session, gm, system, wrap_in_savepoint):
        game_repository = GameRepository(db_session, principal=gm)
        return await game_repository.create(
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

    @pytest.fixture
    def repository(self, db_session, gm):
        return PlayerRepository(db_session, principal=gm)

    async def test_attach_player_to_game_defaults(self, repository, game, create):
        user = await create(ActivatedUserFactory)

        player = await repository.attach_player_to_game(game.id, user.id)

        assert player.game_id == game.id
        assert player.user_id == user.id
        assert player.is_gm is False
        assert player.state == Player.States.APPLIED

    async def test_attach_player_to_game_as_gm(self, repository, game, gm):
        player = await repository.attach_player_to_game(game.id, gm.id, is_gm=True)

        assert player.is_gm is True

    async def test_attach_player_to_game_with_state(self, repository, game, create):
        user = await create(ActivatedUserFactory)

        player = await repository.attach_player_to_game(
            game.id, user.id, state=Player.States.ACCEPTED
        )

        assert player.state == Player.States.ACCEPTED

    async def test_attach_player_to_game_duplicate_raises(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        await repository.attach_player_to_game(game.id, user.id)

        with pytest.raises(DuplicatePlayerError):
            await repository.attach_player_to_game(game.id, user.id)

        # The failed flush leaves the session's transaction unusable; in
        # production this is rolled back by DBSessionDependency at the
        # request boundary, which these repository-level tests bypass.
        await db_session.rollback()

    async def test_get_players_for_game_returns_all_states_by_default(
        self, repository, game, create
    ):
        applied = await create(ActivatedUserFactory)
        accepted = await create(ActivatedUserFactory)
        await repository.attach_player_to_game(game.id, applied.id)
        await repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )

        players = list(await repository.get_players_for_game(game.id))

        assert {p.user_id for p in players} == {applied.id, accepted.id}

    async def test_get_players_for_game_only_accepted_filters_other_states(
        self, repository, game, create
    ):
        applied = await create(ActivatedUserFactory)
        accepted = await create(ActivatedUserFactory)
        await repository.attach_player_to_game(game.id, applied.id)
        await repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )

        players = list(
            await repository.get_players_for_game(game.id, only_accepted=True)
        )

        assert {p.user_id for p in players} == {accepted.id}

    async def test_get_players_for_game_scoped_to_game(
        self, repository, game, gm, system, db_session, create
    ):
        other_game_repository = GameRepository(db_session, principal=gm)
        other_game = await other_game_repository.create(
            "Other Campaign",
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
        user = await create(ActivatedUserFactory)
        await repository.attach_player_to_game(other_game.id, user.id)

        players = list(await repository.get_players_for_game(game.id))

        assert players == []

    async def test_get_players_for_game_eager_loads_user(
        self, repository, game, create
    ):
        user = await create(ActivatedUserFactory)
        await repository.attach_player_to_game(game.id, user.id)

        players = list(await repository.get_players_for_game(game.id))

        # Accessing an unloaded relationship on an async session raises
        # MissingGreenlet, so this only passes if user was eagerly loaded.
        assert players[0].user.username == user.username

    async def test_get_player_returns_player(self, repository, game, create):
        user = await create(ActivatedUserFactory)
        await repository.attach_player_to_game(
            game.id, user.id, state=Player.States.INVITED
        )

        player = await repository.get_player(game.id, user.id)

        assert player is not None
        assert player.state == Player.States.INVITED

    async def test_get_player_none_when_not_a_player(self, repository, game, create):
        user = await create(ActivatedUserFactory)

        assert await repository.get_player(game.id, user.id) is None

    async def test_delete_player_removes_row(self, repository, game, create):
        user = await create(ActivatedUserFactory)
        player = await repository.attach_player_to_game(
            game.id, user.id, state=Player.States.INVITED
        )

        await repository.delete_player(player)

        assert await repository.get_player(game.id, user.id) is None

    async def test_delete_player_removes_only_this_games_role_memberships(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        player = await repository.attach_player_to_game(
            game.id, user.id, state=Player.States.ACCEPTED
        )
        extra_game_role = await create(RoleFactory, game_role=game.id)
        unrelated_role = await create(RoleFactory)
        for role_id in (
            game.gm_role_id,
            game.player_role_id,
            extra_game_role.id,
            unrelated_role.id,
        ):
            db_session.add(UserRole(user_id=user.id, role_id=role_id))
        await db_session.flush()

        await repository.delete_player(player)

        assert await role_ids_of(db_session, user.id) == {unrelated_role.id}

    async def test_update_state_accepting_adds_user_to_player_role(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        player = await repository.attach_player_to_game(game.id, user.id)

        await repository.update_state(player, state=Player.States.ACCEPTED)

        assert await role_ids_of(db_session, user.id) == {game.player_role_id}

    async def test_update_state_non_accept_change_leaves_roles_alone(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        player = await repository.attach_player_to_game(game.id, user.id)

        await repository.update_state(player, state=Player.States.INVITED)

        assert await role_ids_of(db_session, user.id) == set()

    async def test_update_state_promoting_swaps_player_roles_for_gm_role(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        player = await repository.attach_player_to_game(game.id, user.id)
        await repository.update_state(player, state=Player.States.ACCEPTED)
        extra_game_role = await create(RoleFactory, game_role=game.id)
        unrelated_role = await create(RoleFactory)
        for role_id in (extra_game_role.id, unrelated_role.id):
            db_session.add(UserRole(user_id=user.id, role_id=role_id))
        await db_session.flush()

        await repository.update_state(player, is_gm=True)

        assert await role_ids_of(db_session, user.id) == {
            game.gm_role_id,
            unrelated_role.id,
        }

    async def test_update_state_demoting_swaps_gm_role_for_player_role(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        player = await repository.attach_player_to_game(game.id, user.id)
        await repository.update_state(player, state=Player.States.ACCEPTED)
        await repository.update_state(player, is_gm=True)

        await repository.update_state(player, is_gm=False)

        assert await role_ids_of(db_session, user.id) == {game.player_role_id}

    async def test_update_state_accepting_gm_adds_gm_role(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        player = await repository.attach_player_to_game(
            game.id, user.id, is_gm=True, state=Player.States.INVITED
        )

        await repository.update_state(player, state=Player.States.ACCEPTED)

        assert await role_ids_of(db_session, user.id) == {game.gm_role_id}

    async def test_update_state_accepting_revives_soft_deleted_membership(
        self, repository, game, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        db_session.add(
            UserRole(
                user_id=user.id,
                role_id=game.player_role_id,
                deleted=datetime.now(UTC),
            )
        )
        player = await repository.attach_player_to_game(game.id, user.id)

        await repository.update_state(player, state=Player.States.ACCEPTED)

        assert await role_ids_of(db_session, user.id) == {game.player_role_id}

    async def test_is_gm_true_for_gm_player(self, repository, game, gm):
        await repository.attach_player_to_game(game.id, gm.id, is_gm=True)

        assert await repository.is_gm(game.id, gm.id) is True

    async def test_is_gm_false_for_non_gm_player(self, repository, game, create):
        user = await create(ActivatedUserFactory)
        await repository.attach_player_to_game(game.id, user.id, is_gm=False)

        assert await repository.is_gm(game.id, user.id) is False

    async def test_is_gm_false_when_not_a_player(self, repository, game, create):
        user = await create(ActivatedUserFactory)

        assert await repository.is_gm(game.id, user.id) is False
