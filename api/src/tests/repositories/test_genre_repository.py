import pytest

from app.repositories.genre_repository import GenreRepository


class TestGenreRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return GenreRepository(db_session)

    async def test_add_and_get_all(self, repository):
        added = await repository.add("Fantasy")
        await repository.add("Sci-Fi")

        genres = await repository.get_all()

        assert added.id is not None
        assert added.genre == "Fantasy"
        assert {genre.genre for genre in genres} == {"Fantasy", "Sci-Fi"}
