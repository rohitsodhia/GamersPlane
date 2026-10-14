import pytest

from app.models import FAQ
from app.repositories import FAQRepository
from tests.factories import prose_doc

Categories = FAQ.Categories


class TestFAQRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return FAQRepository(db_session)

    async def add(self, repository, category, question):
        return await repository.add(category, question, prose_doc(question))

    async def titles(self, repository, category):
        faqs = [f for f in await repository.get_all() if f.category == category]
        return [(f.question, f.order) for f in faqs]

    async def test_add_appends_to_each_category_independently(self, repository):
        await self.add(repository, Categories.GAMES, "G1")
        await self.add(repository, Categories.GAMES, "G2")
        tool = await self.add(repository, Categories.TOOLS, "T1")

        assert tool.order == 1
        assert await self.titles(repository, Categories.GAMES) == [("G1", 1), ("G2", 2)]

    async def test_update_category_change_appends_and_closes_old_gap(self, repository):
        await self.add(repository, Categories.GAMES, "G1")
        mid = await self.add(repository, Categories.GAMES, "G2")
        await self.add(repository, Categories.GAMES, "G3")
        await self.add(repository, Categories.TOOLS, "T1")

        await repository.update(mid, Categories.TOOLS, "G2 now", prose_doc("x"))

        assert await self.titles(repository, Categories.GAMES) == [("G1", 1), ("G3", 2)]
        assert await self.titles(repository, Categories.TOOLS) == [
            ("T1", 1),
            ("G2 now", 2),
        ]

    async def test_update_same_category_keeps_position(self, repository):
        await self.add(repository, Categories.GAMES, "G1")
        second = await self.add(repository, Categories.GAMES, "G2")

        await repository.update(second, Categories.GAMES, "Renamed", prose_doc("x"))

        assert await self.titles(repository, Categories.GAMES) == [
            ("G1", 1),
            ("Renamed", 2),
        ]

    async def test_delete_closes_gap(self, repository):
        await self.add(repository, Categories.GAMES, "G1")
        mid = await self.add(repository, Categories.GAMES, "G2")
        await self.add(repository, Categories.GAMES, "G3")
        await self.add(repository, Categories.TOOLS, "T1")

        await repository.delete(mid)

        assert await self.titles(repository, Categories.GAMES) == [("G1", 1), ("G3", 2)]
        assert await self.titles(repository, Categories.TOOLS) == [("T1", 1)]

    async def test_move_up_and_down_swap_with_neighbour(self, repository):
        await self.add(repository, Categories.GAMES, "G1")
        second = await self.add(repository, Categories.GAMES, "G2")
        await self.add(repository, Categories.GAMES, "G3")

        await repository.move(second, "up")
        assert [q for q, _ in await self.titles(repository, Categories.GAMES)] == [
            "G2",
            "G1",
            "G3",
        ]

        await repository.move(second, "down")
        await repository.move(second, "down")
        assert [q for q, _ in await self.titles(repository, Categories.GAMES)] == [
            "G1",
            "G3",
            "G2",
        ]

    async def test_move_past_either_end_is_a_no_op(self, repository):
        first = await self.add(repository, Categories.GAMES, "G1")
        last = await self.add(repository, Categories.GAMES, "G2")

        await repository.move(first, "up")
        await repository.move(last, "down")

        assert await self.titles(repository, Categories.GAMES) == [("G1", 1), ("G2", 2)]
