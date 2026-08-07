import pytest

from app.exceptions import NotFoundException
from app.models import Forum
from app.repositories import ForumRepository
from tests.factories import ForumFactory


class TestForumRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ForumRepository(db_session, auth=[])

    async def test_add(self, repository, create):
        parent = await create(ForumFactory, heritage=[])

        forum = await repository.add(
            title="General", forum_type=Forum.ForumTypes.FORUM, parent_id=parent.id
        )

        assert forum.title == "General"
        assert forum.forum_type == Forum.ForumTypes.FORUM
        assert forum.parent_id == parent.id
        assert forum.heritage == [parent.id]
        assert forum.order == 1
        assert forum.game_id is None
        assert forum.description is None

    async def test_add_with_description(self, repository, create):
        parent = await create(ForumFactory, heritage=[])

        forum = await repository.add(
            title="General",
            forum_type=Forum.ForumTypes.CATEGORY,
            parent_id=parent.id,
            description="A description",
        )

        assert forum.description == "A description"

    async def test_add_computes_order_from_existing_children(
        self, repository, create
    ):
        parent = await create(ForumFactory, heritage=[])
        await create(ForumFactory, parent_id=parent.id, order=1)
        await create(ForumFactory, parent_id=parent.id, order=2)

        forum = await repository.add(
            title="Third", forum_type=Forum.ForumTypes.FORUM, parent_id=parent.id
        )

        assert forum.order == 3

    async def test_add_extends_parent_heritage(self, repository, create):
        grandparent = await create(ForumFactory, heritage=[])
        parent = await create(
            ForumFactory, parent_id=grandparent.id, heritage=[grandparent.id]
        )

        forum = await repository.add(
            title="Child", forum_type=Forum.ForumTypes.FORUM, parent_id=parent.id
        )

        assert forum.heritage == [grandparent.id, parent.id]

    async def test_add_parent_not_found(self, repository):
        with pytest.raises(NotFoundException):
            await repository.add(
                title="Orphan", forum_type=Forum.ForumTypes.FORUM, parent_id=999999
            )

    async def test_get(self, repository, create):
        forum = await create(ForumFactory, heritage=[])

        found = await repository.get(forum.id)

        assert found is not None
        assert found.id == forum.id

    async def test_get_not_found(self, repository):
        found = await repository.get(999999)

        assert found is None

    async def test_get_multiple(self, repository, create):
        first = await create(ForumFactory, heritage=[])
        second = await create(ForumFactory, heritage=[])
        await create(ForumFactory, heritage=[])

        found = await repository.get_multiple([first.id, second.id])

        assert {forum.id for forum in found} == {first.id, second.id}

    async def test_get_multiple_empty(self, repository, create):
        await create(ForumFactory, heritage=[])

        found = await repository.get_multiple([])

        assert list(found) == []

    async def test_get_descendants(self, repository, create):
        root = await create(ForumFactory, heritage=[])
        child = await create(
            ForumFactory, parent_id=root.id, heritage=[root.id], order=1
        )
        grandchild = await create(
            ForumFactory,
            parent_id=child.id,
            heritage=[root.id, child.id],
            order=1,
        )
        await create(ForumFactory, heritage=[])

        descendants = list(await repository.get_descendants(root.id))

        assert {forum.id for forum in descendants} == {child.id, grandchild.id}

    async def test_get_descendants_orders_by_order(self, repository, create):
        root = await create(ForumFactory, heritage=[])
        await create(
            ForumFactory, parent_id=root.id, heritage=[root.id], order=2, title="B"
        )
        await create(
            ForumFactory, parent_id=root.id, heritage=[root.id], order=1, title="A"
        )

        descendants = list(await repository.get_descendants(root.id))

        assert [forum.title for forum in descendants] == ["A", "B"]

    async def test_get_descendants_empty(self, repository, create):
        root = await create(ForumFactory, heritage=[])

        descendants = list(await repository.get_descendants(root.id))

        assert descendants == []
