from app.models import Forum
from tests.factories import ForumFactory


class TestGetForum:
    async def test_get_forum_is_public(self, client, create):
        forum = await create(ForumFactory, heritage=[])

        response = await client.get(f"/forums/{forum.id}")

        assert response.status_code == 200

    async def test_get_forum_not_found(self, client):
        response = await client.get("/forums/999999")

        assert response.status_code == 404

    async def test_get_forum_returns_fields(self, client, create):
        forum = await create(
            ForumFactory,
            title="General",
            description="General discussion",
            forum_type=Forum.ForumTypes.FORUM,
            heritage=[],
            order=1,
            thread_count=5,
        )

        response = await client.get(f"/forums/{forum.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == forum.id
        assert body["title"] == "General"
        assert body["description"] == "General discussion"
        assert body["forum_type"] == "f"
        assert body["parent_id"] is None
        assert body["heritage"] == []
        assert body["order"] == 1
        assert body["game_id"] is None
        assert body["thread_count"] == 5
        assert body["children"] == []

    async def test_get_forum_includes_heritage(self, client, create):
        grandparent = await create(
            ForumFactory, title="Grandparent", heritage=[], order=1
        )
        parent = await create(
            ForumFactory,
            title="Parent",
            parent_id=grandparent.id,
            heritage=[grandparent.id],
            order=1,
        )
        forum = await create(
            ForumFactory,
            title="Forum",
            parent_id=parent.id,
            heritage=[grandparent.id, parent.id],
            order=1,
        )

        response = await client.get(f"/forums/{forum.id}")

        body = response.json()
        assert body["heritage"] == [
            {"id": grandparent.id, "title": "Grandparent"},
            {"id": parent.id, "title": "Parent"},
        ]

    async def test_get_forum_missing_heritage_forum_returns_404(
        self, client, create
    ):
        forum = await create(ForumFactory, heritage=[999999])

        response = await client.get(f"/forums/{forum.id}")

        assert response.status_code == 404

    async def test_get_forum_includes_children_tree(self, client, create):
        root = await create(ForumFactory, title="Root", heritage=[], order=1)
        child = await create(
            ForumFactory,
            title="Child",
            parent_id=root.id,
            heritage=[root.id],
            order=1,
        )
        await create(
            ForumFactory,
            title="Grandchild",
            parent_id=child.id,
            heritage=[root.id, child.id],
            order=1,
        )

        response = await client.get(f"/forums/{root.id}")

        body = response.json()
        assert len(body["children"]) == 1
        assert body["children"][0]["title"] == "Child"
        assert len(body["children"][0]["children"]) == 1
        assert body["children"][0]["children"][0]["title"] == "Grandchild"

    async def test_get_forum_no_children(self, client, create):
        forum = await create(ForumFactory, heritage=[])

        response = await client.get(f"/forums/{forum.id}")

        assert response.json()["children"] == []
