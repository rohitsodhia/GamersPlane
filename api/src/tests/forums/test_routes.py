from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from app.models import FavoriteGame, Forum, Player, Role, RolePermission
from app.repositories import GameRepository, ThreadRepository
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    PostFactory,
    RoleFactory,
    SystemFactory,
    ThreadFactory,
)
from tests.rbac.test_routes import make_game_backed_by

Verbs = RolePermission.ValidPermissions
ALLOW = RolePermission.Effects.ALLOW
DENY = RolePermission.Effects.DENY


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
            {"id": grandparent.id, "title": "Grandparent", "moderate": False},
            {"id": parent.id, "title": "Parent", "moderate": False},
        ]

    async def test_get_forum_heritage_flags_moderated_ancestors(
        self, authed_client, db_session, create, open_forums
    ):
        client, user = authed_client
        grandparent = await create(ForumFactory, title="Top", heritage=[])
        parent = await create(
            ForumFactory,
            parent_id=grandparent.id,
            heritage=[grandparent.id],
            title="Mid",
        )
        forum = await create(
            ForumFactory,
            parent_id=parent.id,
            heritage=[grandparent.id, parent.id],
            title="Leaf",
        )
        await open_forums(grandparent.id)
        await grant_role(db_session, user, (Verbs.FORUM_MODERATE, parent.id, ALLOW))

        response = await client.get(f"/forums/{forum.id}")

        assert [(h["id"], h["moderate"]) for h in response.json()["heritage"]] == [
            (grandparent.id, False),
            (parent.id, True),
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


@pytest.fixture
async def site(create, db_session, open_forums, wrap_in_savepoint):
    index = await create(ForumFactory, id=0, heritage=[], title="Index")
    games_root = await create(
        ForumFactory, id=GAMES_ROOT_FORUM_ID, parent_id=0, heritage=[0], title="Games"
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
async def gm(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def make_game(create, db_session, gm):
    system = await create(SystemFactory)

    async def _make_game(title, *, public=True):
        return await GameRepository(db_session, principal=gm).create(
            title, system.id, [], gm.id, "1/d", 4, 1, None, None, public, None, None
        )

    return _make_game


class TestForumIndexGames:
    """The index and games forum list only the user's own and favorited games."""

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


async def grant_role(db_session, user, *grants):
    """Give ``user`` a role holding ``(verb, forum_id, effect)`` grants; a
    ``None`` forum id makes the grant global."""
    role = RoleFactory.build()
    db_session.add(role)
    for verb, forum_id, effect in grants:
        role.grant(
            verb,
            scope_type=None if forum_id is None else RolePermission.ScopeTypes.FORUM,
            scope_id=forum_id,
            effect=effect,
        )
    role.users.append(user)
    await db_session.flush()


class TestModeratorModeHeader:
    async def test_header_switches_a_game_forum_between_player_and_moderator_mode(
        self, authed_client, db_session, create, open_forums
    ):
        client, user = authed_client
        site_forum = await create(ForumFactory, heritage=[])
        game = await make_game_backed_by(db_session, create)
        game_forum = await create(
            ForumFactory,
            parent_id=site_forum.id,
            heritage=[site_forum.id],
            game_id=game.id,
        )
        await open_forums(site_forum.id)
        await grant_role(db_session, user, (Verbs.FORUM_MODERATE, site_forum.id, ALLOW))
        url = f"/forums/{game_forum.id}"

        player = (await client.get(url)).json()["permissions"]
        moderator = (await client.get(url, headers={"X-Moderator-Mode": "1"})).json()[
            "permissions"
        ]

        assert "forum_moderate" not in player
        assert "forum_read" in player
        assert "forum_moderate" in moderator


class TestGetModeratedForums:
    @pytest.fixture
    async def general(self, create, site):
        """Index -> General -> Announcements -> Archive."""
        index, _games_root = site
        general = await create(
            ForumFactory, parent_id=index.id, heritage=[index.id], title="General"
        )
        announcements = await create(
            ForumFactory,
            parent_id=general.id,
            heritage=[index.id, general.id],
            title="Announcements",
        )
        archive = await create(
            ForumFactory,
            parent_id=announcements.id,
            heritage=[index.id, general.id, announcements.id],
            title="Archive",
        )
        return general, announcements, archive

    async def test_requires_auth(self, client):
        response = await client.get("/forums/moderated")

        assert response.status_code == 403

    async def test_non_moderator_gets_nothing(self, authed_client, general):
        client, _user = authed_client

        response = await client.get("/forums/moderated")

        assert response.status_code == 200
        assert response.json() == []

    async def test_moderated_forum_nests_under_heading_with_its_subforums(
        self, authed_client, db_session, general
    ):
        client, user = authed_client
        general_forum, announcements, archive = general
        await grant_role(
            db_session, user, (Verbs.FORUM_MODERATE, announcements.id, ALLOW)
        )

        response = await client.get("/forums/moderated")

        assert response.json() == [
            {
                "id": general_forum.id,
                "title": "General",
                "moderate": False,
                "children": [
                    {
                        "id": announcements.id,
                        "title": "Announcements",
                        "moderate": True,
                        "children": [
                            {
                                "id": archive.id,
                                "title": "Archive",
                                "moderate": True,
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]

    async def test_denied_subforum_is_left_out(
        self, authed_client, db_session, general
    ):
        client, user = authed_client
        _general, announcements, archive = general
        await grant_role(
            db_session,
            user,
            (Verbs.FORUM_MODERATE, announcements.id, ALLOW),
            (Verbs.FORUM_MODERATE, archive.id, DENY),
        )

        response = await client.get("/forums/moderated")

        [heading] = response.json()
        assert heading["children"][0]["children"] == []

    async def test_overlapping_moderation_lists_each_forum_once(
        self, authed_client, db_session, general
    ):
        client, user = authed_client
        general_forum, announcements, _archive = general
        await grant_role(
            db_session,
            user,
            (Verbs.FORUM_MODERATE, general_forum.id, ALLOW),
            (Verbs.FORUM_MODERATE, announcements.id, ALLOW),
        )

        response = await client.get("/forums/moderated")

        [heading] = response.json()
        assert heading["moderate"] is True
        [child] = heading["children"]
        assert child["id"] == announcements.id
        assert len(child["children"]) == 1

    async def test_admin_gets_top_level_forums_but_not_other_peoples_games(
        self, authed_client, db_session, site, make_game
    ):
        client, user = authed_client
        await make_game("Stranger's")
        await grant_role(db_session, user, (Verbs.ADMIN, None, ALLOW))

        response = await client.get("/forums/moderated")

        [games] = response.json()
        assert games["title"] == "Games"
        assert games["moderate"] is True
        assert games["children"] == []

    async def test_admin_who_gms_a_game_gets_that_game(
        self, auth_as, db_session, site, make_game, gm
    ):
        game = await make_game("Mine")
        await grant_role(db_session, gm, (Verbs.ADMIN, None, ALLOW))
        client = auth_as(gm)

        response = await client.get("/forums/moderated")

        [games] = response.json()
        assert [f["id"] for f in games["children"]] == [game.root_forum_id]

    async def test_gm_gets_their_game_forum_under_the_games_heading(
        self, auth_as, site, make_game, gm
    ):
        game = await make_game("Mine")
        client = auth_as(gm)

        response = await client.get("/forums/moderated")

        [games] = response.json()
        assert games["title"] == "Games"
        assert games["moderate"] is False
        [game_forum] = games["children"]
        assert game_forum["id"] == game.root_forum_id
        assert game_forum["moderate"] is True


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
            {"id": grandparent.id, "title": "Grandparent", "moderate": False},
            {"id": parent.id, "title": "Parent", "moderate": False},
        ]

    async def test_missing_heritage_forum_returns_404(self, client, create):
        forum = await create(ForumFactory, heritage=[999999])

        response = await client.get(f"/forums/{forum.id}/breadcrumbs")

        assert response.status_code == 404


@pytest.fixture
async def board(create, db_session, site):
    """Index -> General (1) -> Announcements (3), Lounge -> Off Topic, Chat.

    General and Announcements take their protected ids explicitly.
    """
    general = await create(
        ForumFactory, id=1, parent_id=0, heritage=[0], title="General", order=1
    )
    announcements = await create(
        ForumFactory,
        id=3,
        parent_id=general.id,
        heritage=[0, general.id],
        title="Announcements",
        order=1,
    )
    await db_session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
            "(SELECT MAX(id) FROM forums))"
        )
    )
    lounge = await create(
        ForumFactory,
        parent_id=general.id,
        heritage=[0, general.id],
        title="Lounge",
        description="Old",
        order=2,
    )
    off_topic = await create(
        ForumFactory,
        parent_id=lounge.id,
        heritage=[0, general.id, lounge.id],
        title="Off Topic",
        order=1,
    )
    chat = await create(
        ForumFactory,
        parent_id=general.id,
        heritage=[0, general.id],
        title="Chat",
        order=3,
    )
    return {
        "general": general,
        "announcements": announcements,
        "lounge": lounge,
        "off_topic": off_topic,
        "chat": chat,
    }


@pytest.fixture
async def moderator(authed_client, db_session, board):
    """A client whose user moderates General."""
    client, user = authed_client
    await grant_role(
        db_session, user, (Verbs.FORUM_MODERATE, board["general"].id, ALLOW)
    )
    return client


@pytest.fixture
async def admin(authed_client, db_session, board):
    client, user = authed_client
    await grant_role(db_session, user, (Verbs.ADMIN, None, ALLOW))
    return client


async def deleted_at(db_session, forum):
    return await db_session.scalar(
        select(Forum.deleted)
        .where(Forum.id == forum.id)
        .execution_options(skip_filter=True)
    )


class TestUpdateForum:
    async def test_moderator_renames_and_clears_description(
        self, moderator, db_session, board
    ):
        lounge = board["lounge"]

        response = await moderator.patch(
            f"/forums/{lounge.id}", json={"title": "  Hangout ", "description": ""}
        )

        assert response.status_code == 204
        await db_session.refresh(lounge)
        assert (lounge.title, lounge.description) == ("Hangout", None)

    async def test_non_moderator_is_forbidden(self, authed_client, board):
        client, _user = authed_client

        response = await client.patch(
            f"/forums/{board['lounge'].id}", json={"title": "Hangout"}
        )

        assert response.status_code == 403

    async def test_unreadable_forum_is_not_found(
        self, authed_client, db_session, board
    ):
        client, _user = authed_client
        lounge = board["lounge"]
        # Registered is what opens the board, so the deny goes on Registered;
        # another role's deny wouldn't cancel its allow.
        db_session.add(
            RolePermission(
                role_id=Role.REGISTERED_ID,
                permission=Verbs.FORUM_READ,
                scope_type=RolePermission.ScopeTypes.FORUM,
                scope_id=lounge.id,
                effect=DENY,
            )
        )
        await db_session.flush()

        response = await client.patch(f"/forums/{lounge.id}", json={"title": "Hangout"})

        assert response.status_code == 404

    async def test_protected_forum_cant_be_renamed(self, admin, board):
        response = await admin.patch(
            f"/forums/{board['general'].id}", json={"title": "Renamed"}
        )

        assert response.status_code == 403

    async def test_protected_forum_description_changes_alongside_its_own_title(
        self, admin, db_session, board
    ):
        general = board["general"]

        response = await admin.patch(
            f"/forums/{general.id}", json={"title": "General", "description": "New"}
        )

        assert response.status_code == 204
        await db_session.refresh(general)
        assert general.description == "New"

    async def test_game_forum_cant_be_edited(self, auth_as, site, make_game, gm):
        game = await make_game("Mine")

        response = await auth_as(gm).patch(
            f"/forums/{game.root_forum_id}", json={"description": "New"}
        )

        assert response.status_code == 403

    async def test_forum_index_cant_be_edited(self, admin, board):
        response = await admin.patch("/forums/0", json={"description": "New"})

        assert response.status_code == 403


class TestCreateSubforum:
    async def test_moderator_adds_subforum_after_the_last_one(
        self, moderator, db_session, board
    ):
        general = board["general"]

        response = await moderator.post(
            f"/forums/{general.id}/subforums", json={"title": "New"}
        )

        forum = await db_session.get(Forum, response.json()["id"])
        assert (forum.parent_id, forum.heritage, forum.order, forum.game_id) == (
            general.id,
            [0, general.id],
            board["chat"].order + 1,
            None,
        )

    async def test_order_counts_past_a_deleted_subforum(
        self, moderator, db_session, board
    ):
        chat = board["chat"]
        await moderator.delete(f"/forums/{chat.id}")

        response = await moderator.post(
            f"/forums/{board['general'].id}/subforums", json={"title": "New"}
        )

        forum = await db_session.get(Forum, response.json()["id"])
        assert forum.order == chat.order + 1

    async def test_subforum_of_game_forum_belongs_to_the_game(
        self, auth_as, db_session, site, make_game, gm
    ):
        game = await make_game("Mine")

        response = await auth_as(gm).post(
            f"/forums/{game.root_forum_id}/subforums", json={"title": "OOC"}
        )

        forum = await db_session.get(Forum, response.json()["id"])
        assert forum.game_id == game.id

    async def test_non_moderator_is_forbidden(self, authed_client, board):
        client, _user = authed_client

        response = await client.post(
            f"/forums/{board['general'].id}/subforums", json={"title": "New"}
        )

        assert response.status_code == 403


class TestReorderSubforums:
    async def test_listed_subforums_swap_their_slots(
        self, moderator, db_session, board
    ):
        announcements, lounge, chat = (
            board["announcements"],
            board["lounge"],
            board["chat"],
        )

        response = await moderator.put(
            f"/forums/{board['general'].id}/subforums/order",
            json={"forum_ids": [chat.id, announcements.id]},
        )

        assert response.status_code == 204
        for forum in (announcements, lounge, chat):
            await db_session.refresh(forum)
        assert (chat.order, lounge.order, announcements.order) == (1, 2, 3)

    @pytest.mark.parametrize(
        "listed", [["announcements", "announcements"], ["announcements", "off_topic"]]
    )
    async def test_duplicate_or_foreign_forum_is_rejected(
        self, moderator, board, listed
    ):
        response = await moderator.put(
            f"/forums/{board['general'].id}/subforums/order",
            json={"forum_ids": [board[name].id for name in listed]},
        )

        assert response.status_code == 400

    async def test_non_moderator_is_forbidden(self, authed_client, board):
        client, _user = authed_client

        response = await client.put(
            f"/forums/{board['general'].id}/subforums/order",
            json={"forum_ids": [board["chat"].id]},
        )

        assert response.status_code == 403


class TestDeleteForum:
    async def test_soft_deletes_forum_and_its_subforums_together(
        self, moderator, db_session, board
    ):
        response = await moderator.delete(f"/forums/{board['lounge'].id}")

        assert response.status_code == 204
        lounge_deleted = await deleted_at(db_session, board["lounge"])
        assert lounge_deleted is not None
        assert await deleted_at(db_session, board["off_topic"]) == lounge_deleted
        assert await deleted_at(db_session, board["chat"]) is None

    async def test_moderating_only_the_forum_itself_isnt_enough(
        self, authed_client, db_session, board
    ):
        client, user = authed_client
        lounge = board["lounge"]
        await grant_role(db_session, user, (Verbs.FORUM_MODERATE, lounge.id, ALLOW))

        response = await client.delete(f"/forums/{lounge.id}")

        assert response.status_code == 403

    async def test_protected_forum_cant_be_deleted(self, admin, board):
        response = await admin.delete(f"/forums/{board['announcements'].id}")

        assert response.status_code == 403

    async def test_game_forum_cant_be_deleted(self, admin, make_game):
        game = await make_game("Mine")

        response = await admin.delete(f"/forums/{game.root_forum_id}")

        assert response.status_code == 403


async def add_unread_thread(create, db_session, forum):
    thread = await create(ThreadFactory, forum=forum)
    post = await create(
        PostFactory, thread=thread, published_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    await ThreadRepository(db_session, principal=None).attach_new_post(thread, post)
    return thread


def child_flags(children):
    """``{forum id: has_unread}`` for every forum in a children tree."""
    flags = {}
    for child in children:
        flags[child["id"]] = child["has_unread"]
        flags.update(child_flags(child["children"]))
    return flags


@pytest.fixture
async def unread_tree(create, db_session, site):
    """Index > top > sub (holding an unread thread), plus an empty sibling."""
    top = await create(ForumFactory, parent_id=0, heritage=[0])
    sub = await create(ForumFactory, parent_id=top.id, heritage=[0, top.id])
    quiet = await create(ForumFactory, parent_id=0, heritage=[0])
    await add_unread_thread(create, db_session, sub)
    return top, sub, quiet


class TestForumUnreadFlags:
    async def test_unread_thread_flags_its_forum_and_ancestors(
        self, authed_client, unread_tree
    ):
        client, _user = authed_client
        top, sub, quiet = unread_tree

        body = (await client.get("/forums/0")).json()

        flags = child_flags(body["children"])
        assert flags[top.id] is True
        assert flags[sub.id] is True
        assert flags[quiet.id] is False
        assert body["has_unread"] is True

    async def test_guests_never_see_unread(self, client, unread_tree):
        top, sub, quiet = unread_tree

        body = (await client.get("/forums/0")).json()

        flags = child_flags(body["children"])
        assert set(flags) >= {top.id, sub.id, quiet.id}
        assert not any(flags.values())
        assert body["has_unread"] is False


class TestMarkForumRead:
    async def test_requires_auth(self, client, unread_tree):
        top, _sub, _quiet = unread_tree

        response = await client.post(f"/forums/{top.id}/mark-read")

        assert response.status_code == 403

    async def test_marks_the_forum_and_its_subforums_read(
        self, authed_client, unread_tree
    ):
        client, _user = authed_client
        top, sub, _quiet = unread_tree

        response = await client.post(f"/forums/{top.id}/mark-read")

        assert response.status_code == 204
        flags = child_flags((await client.get("/forums/0")).json()["children"])
        assert flags[top.id] is False
        assert flags[sub.id] is False

    async def test_forum_unreadable_itself_but_leading_to_a_readable_one_is_allowed(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        heading = await create(ForumFactory, heritage=[])
        leaf = await create(ForumFactory, parent_id=heading.id, heritage=[heading.id])
        await grant_role(db_session, user, (Verbs.FORUM_READ, leaf.id, ALLOW))

        response = await client.post(f"/forums/{heading.id}/mark-read")

        assert response.status_code == 204

    async def test_forum_with_nothing_readable_returns_404(self, authed_client, create):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[])

        response = await client.post(f"/forums/{forum.id}/mark-read")

        assert response.status_code == 404
