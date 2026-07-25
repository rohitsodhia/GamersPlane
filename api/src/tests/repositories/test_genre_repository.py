import pytest

from app.repositories.genre_repository import GenreRepository


class TestGenreRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return GenreRepository(db_session)

    async def test_add(self, repository):
        genre = await repository.add("Fantasy")

        assert genre.id is not None
        assert genre.genre == "Fantasy"

    async def test_get_all(self, repository):
        await repository.add("Fantasy")
        await repository.add("Sci-Fi")

        genres = await repository.get_all()

        assert {genre.genre for genre in genres} == {"Fantasy", "Sci-Fi"}

    async def test_get_all_empty(self, repository):
        genres = await repository.get_all()

        assert genres == []
