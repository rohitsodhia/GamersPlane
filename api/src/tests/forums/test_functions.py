import pytest

from app.exceptions import NotFoundException
from app.forums.functions import build_forum_tree, get_heritage
from app.models import Forum
from app.repositories import ForumRepository
from tests.factories import ForumFactory


class TestGetHeritage:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ForumRepository(db_session, auth=[])

    async def test_get_heritage_returns_ordered_list(self, repository, create):
        grandparent = await create(ForumFactory, heritage=[], title="Grandparent")
        parent = await create(
            ForumFactory,
            parent_id=grandparent.id,
            heritage=[grandparent.id],
            title="Parent",
        )

        heritage = await get_heritage(repository, [grandparent.id, parent.id])

        assert [forum.title for forum in heritage] == ["Grandparent", "Parent"]

    async def test_get_heritage_empty(self, repository):
        heritage = await get_heritage(repository, [])

        assert heritage == []

    async def test_get_heritage_missing_forum_raises(self, repository, create):
        grandparent = await create(ForumFactory, heritage=[], title="Grandparent")

        with pytest.raises(NotFoundException):
            await get_heritage(repository, [grandparent.id, 999999])


class TestBuildForumTree:
    def make_forum(self, id, parent_id, title="Forum"):
        return Forum(
            id=id,
            title=title,
            forum_type=Forum.ForumTypes.FORUM,
            parent_id=parent_id,
            heritage=[],
            order=1,
            thread_count=0,
        )

    def test_build_forum_tree_empty(self):
        tree = build_forum_tree([], 1)

        assert tree == []

    def test_build_forum_tree_single_level(self):
        descendants = [self.make_forum(2, 1, "Child")]

        tree = build_forum_tree(descendants, 1)

        assert len(tree) == 1
        assert tree[0].id == 2
        assert tree[0].title == "Child"
        assert tree[0].children == []

    def test_build_forum_tree_nested(self):
        descendants = [
            self.make_forum(2, 1, "Child"),
            self.make_forum(3, 2, "Grandchild"),
        ]

        tree = build_forum_tree(descendants, 1)

        assert len(tree) == 1
        assert tree[0].id == 2
        assert len(tree[0].children) == 1
        assert tree[0].children[0].id == 3
        assert tree[0].children[0].title == "Grandchild"

    def test_build_forum_tree_excludes_unrelated_branches(self):
        descendants = [
            self.make_forum(2, 1, "Child"),
            self.make_forum(3, 99, "Unrelated"),
        ]

        tree = build_forum_tree(descendants, 1)

        assert [forum.id for forum in tree] == [2]
