import pytest
from sqlalchemy import text

from app.models import FavoriteGame
from app.repositories import FavoritesRepository, GameRepository
from tests.factories import ActivatedUserFactory, ForumFactory, SystemFactory


class TestToggleGameFavorite:
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
    async def user(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def game(self, db_session, user, system):
        game_repository = GameRepository(db_session, principal=user)
        return await game_repository.create(
            "My Campaign",
            system.id,
            [],
            user.id,
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
    def repository(self, db_session, user, wrap_in_savepoint):
        return FavoritesRepository(db_session, user)

    async def test_toggle_creates_favorite_when_none_exists(
        self, repository, db_session, user, game
    ):
        result = await repository.toggle_game_favorite(game.id)

        assert result is True
        favorite = await db_session.get(FavoriteGame, (user.id, game.id))
        assert favorite is not None

    async def test_toggle_removes_favorite_when_one_exists(
        self, repository, db_session, user, game
    ):
        await repository.toggle_game_favorite(game.id)

        result = await repository.toggle_game_favorite(game.id)

        assert result is False
        favorite = await db_session.get(FavoriteGame, (user.id, game.id))
        assert favorite is None

    async def test_toggle_is_scoped_to_the_principal(
        self, repository, db_session, user, game, create
    ):
        other_user = await create(ActivatedUserFactory)
        other_repository = FavoritesRepository(db_session, other_user)
        await other_repository.toggle_game_favorite(game.id)

        result = await repository.toggle_game_favorite(game.id)

        assert result is True
        assert await db_session.get(FavoriteGame, (other_user.id, game.id)) is not None
        assert await db_session.get(FavoriteGame, (user.id, game.id)) is not None
