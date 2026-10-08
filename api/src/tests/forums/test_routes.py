from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.models import FavoriteGame, Forum, Player, RolePermission
from app.repositories import GameRepository
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID
from tests.factories import ActivatedUserFactory, ForumFactory, SystemFactory


class TestGetForum:
    async def test_get_forum_is_public(self, client, create, open_forums):
        forum = await create(ForumFactory, heritage=[])
        await open_forums(forum.id)

        response = await client.get(f"/forums/{forum.id}")

        assert response.status_code == 200

    async def test_get_forum_not_found(self, client):
        response = await client.get("/forums/999999")

        assert response.status_code == 404

    async def test_get_forum_returns_fields(self, client, create, open_forums):
        forum = await create(
            ForumFactory,
            title="General",
            description="General discussion",
            forum_type=Forum.ForumTypes.FORUM,
            heritage=[],
            order=1,
            thread_count=5,
        )
        await open_forums(forum.id)

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
        assert body["permissions"] == ["forum_read"]
        assert body["children"] == []

    async def test_get_forum_includes_heritage(self, client, create, open_forums):
        grandparent = await create(
            ForumFactory, title="Grandparent", heritage=[], order=1
        )
        await open_forums(grandparent.id)
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

    async def test_get_forum_missing_heritage_forum_returns_404(self, client, create):
        forum = await create(ForumFactory, heritage=[999999])

        response = await client.get(f"/forums/{forum.id}")

        assert response.status_code == 404

    async def test_get_forum_includes_children_tree(self, client, create, open_forums):
        root = await create(ForumFactory, title="Root", heritage=[], order=1)
        await open_forums(root.id)
        await create(
            ForumFactory,
            title="Child",
            parent_id=root.id,
            heritage=[root.id],
            order=1,
        )

        response = await client.get(f"/forums/{root.id}")

        body = response.json()
        assert len(body["children"]) == 1
        assert body["children"][0]["title"] == "Child"

    async def test_get_forum_no_children(self, client, create, open_forums):
        forum = await create(ForumFactory, heritage=[])
        await open_forums(forum.id)

        response = await client.get(f"/forums/{forum.id}")

        assert response.json()["children"] == []


class TestGetForumVisibility:
    async def test_unreadable_forum_without_readable_subforums_returns_404(
        self, client, create, open_forums
    ):
        forum = await create(ForumFactory, heritage=[])
        await open_forums()

        response = await client.get(f"/forums/{forum.id}")

        assert response.status_code == 404

    async def test_unreadable_forum_shows_as_heading_over_readable_subforum(
        self, client, create, open_forums
    ):
        parent = await create(ForumFactory, heritage=[], thread_count=3)
        child = await create(
            ForumFactory, parent_id=parent.id, heritage=[parent.id], title="Open"
        )
        await open_forums(child.id)

        response = await client.get(f"/forums/{parent.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["permissions"] == []
        assert body["thread_count"] == 0
        assert [c["title"] for c in body["children"]] == ["Open"]

    async def test_unreadable_subforums_are_left_out(
        self, client, create, db_session, open_forums
    ):
        parent = await create(ForumFactory, heritage=[])
        await create(
            ForumFactory, parent_id=parent.id, heritage=[parent.id], title="Shown"
        )
        hidden = await create(ForumFactory, parent_id=parent.id, heritage=[parent.id])
        _registered, guest = await open_forums(parent.id)
        guest.grant(
            RolePermission.ValidPermissions.FORUM_READ,
            scope_type=RolePermission.ScopeTypes.FORUM,
            scope_id=hidden.id,
            effect=RolePermission.Effects.DENY,
        )
        await db_session.flush()

        response = await client.get(f"/forums/{parent.id}")

        assert [c["title"] for c in response.json()["children"]] == ["Shown"]


class TestForumIndexGames:
    """The index and games forum list only the user's own and favorited games."""

    @pytest.fixture
    async def site(self, create, db_session, open_forums, wrap_in_savepoint):
        index = await create(ForumFactory, id=0, heritage=[], title="Index")
        games_root = await create(
            ForumFactory, id=GAMES_ROOT_FORUM_ID, parent_id=0, heritage=[0]
        )
        # Explicit ids bypass the forums sequence; resync it so later forums
        # don't collide.
        await db_session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
                "(SELECT MAX(id) FROM forums))"
            )
        )
        await open_forums(index.id)
        return index, games_root

    @pytest.fixture
    async def make_game(self, create, db_session):
        system = await create(SystemFactory)
        gm = await create(ActivatedUserFactory)

        async def _make_game(title, *, public=True):
            return await GameRepository(db_session, principal=gm).create(
                title, system.id, [], gm.id, "1/d", 4, 1, None, None, public, None, None
            )

        return _make_game

    async def test_logged_in_user_sees_only_played_and_favorited_games(
        self, authed_client, site, make_game, db_session
    ):
        client, user = authed_client
        _index, games_root = site
        played = await make_game("Played")
        favorited = await make_game("Favorited")
        await make_game("Stranger's")
        retired = await make_game("Retired")
        retired.retired = datetime.now(UTC)
        db_session.add_all(
            [
                Player(
                    game_id=played.id,
                    user_id=user.id,
                    state=Player.States.ACCEPTED,
                ),
                Player(
                    game_id=retired.id,
                    user_id=user.id,
                    state=Player.States.ACCEPTED,
                ),
                FavoriteGame(user_id=user.id, game_id=favorited.id),
            ]
        )
        await db_session.flush()

        response = await client.get(f"/forums/{games_root.id}")

        titles = {c["title"] for c in response.json()["children"]}
        assert titles == {"Played", "Favorited"}

    async def test_anonymous_user_sees_no_game_forums(self, client, site, make_game):
        _index, games_root = site
        await make_game("Public Game")

        response = await client.get(f"/forums/{games_root.id}")

        assert response.json()["children"] == []

    async def test_unlisted_public_game_forum_is_readable_by_direct_link(
        self, client, site, make_game
    ):
        game = await make_game("Public Game")

        response = await client.get(f"/forums/{game.root_forum_id}")

        assert response.status_code == 200
        assert response.json()["permissions"] == ["forum_read"]


class TestGetForumBreadcrumbs:
    async def test_is_public(self, client, create, open_forums):
        forum = await create(ForumFactory, heritage=[])
        await open_forums(forum.id)

        response = await client.get(f"/forums/{forum.id}/breadcrumbs")

        assert response.status_code == 200

    async def test_not_found(self, client):
        response = await client.get("/forums/999999/breadcrumbs")

        assert response.status_code == 404

    async def test_returns_id_and_title_with_empty_heritage(
        self, client, create, open_forums
    ):
        forum = await create(ForumFactory, title="General", heritage=[])
        await open_forums(forum.id)

        response = await client.get(f"/forums/{forum.id}/breadcrumbs")

        assert response.json() == {"id": forum.id, "title": "General", "heritage": []}

    async def test_includes_heritage_in_order(self, client, create, open_forums):
        grandparent = await create(
            ForumFactory, title="Grandparent", heritage=[], order=1
        )
        await open_forums(grandparent.id)
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

        response = await client.get(f"/forums/{forum.id}/breadcrumbs")

        assert response.json()["heritage"] == [
            {"id": grandparent.id, "title": "Grandparent"},
            {"id": parent.id, "title": "Parent"},
        ]

    async def test_missing_heritage_forum_returns_404(self, client, create):
        forum = await create(ForumFactory, heritage=[999999])

        response = await client.get(f"/forums/{forum.id}/breadcrumbs")

        assert response.status_code == 404
