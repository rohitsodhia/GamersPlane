from datetime import date, datetime, timedelta, timezone

from app.configs import configs
from app.models import RolePermission, UserMeta
from app.repositories.user_repository import UserRepository
from tests.factories import (
    ActivatedUserFactory,
    PostFactory,
    RoleFactory,
    ThreadFactory,
    UserFactory,
)

Verbs = RolePermission.ValidPermissions


async def give_permission(db_session, user, verb):
    """Attach a role holding one global grant so the auth middleware sees it."""
    role = RoleFactory.build(owner=user)
    db_session.add(role)
    role.grant(verb)
    user.roles.append(role)
    await db_session.flush()
    return role


class TestSearchUser:
    async def test_search_user_requires_auth(self, client):
        response = await client.get("/users/search", params={"username": "someone"})

        assert response.status_code == 403

    async def test_search_user_found(self, authed_client, create):
        client, _user = authed_client
        other = await create(ActivatedUserFactory, username="findme")

        response = await client.get("/users/search", params={"username": "findme"})

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == other.id
        assert body["user"]["username"] == other.username

    async def test_search_user_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.get("/users/search", params={"username": "nobody"})

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "user_not_found"

    async def test_search_user_by_id_found(self, authed_client, create):
        client, _user = authed_client
        other = await create(ActivatedUserFactory, username="findme")

        response = await client.get("/users/search", params={"id": other.id})

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == other.id
        assert body["user"]["username"] == other.username

    async def test_search_user_by_id_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.get("/users/search", params={"id": 999999})

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "user_not_found"

    async def test_search_user_missing_query(self, authed_client):
        client, _user = authed_client

        response = await client.get("/users/search")

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "missing_query"


class TestAutocompleteUsers:
    async def test_requires_auth(self, client):
        response = await client.get("/users/autocomplete", params={"username": "user"})

        assert response.status_code == 403

    async def test_returns_prefix_matches_case_insensitively_sorted(
        self, authed_client, create
    ):
        client, _user = authed_client
        await create(ActivatedUserFactory, username="Zeta")
        await create(ActivatedUserFactory, username="zebra")
        await create(ActivatedUserFactory, username="zoo")

        response = await client.get("/users/autocomplete", params={"username": "ZE"})

        assert response.status_code == 200
        assert [u["username"] for u in response.json()["users"]] == [
            "zebra",
            "Zeta",
        ]

    async def test_excludes_unactivated_users(self, authed_client, create):
        client, _user = authed_client
        await create(UserFactory, username="pending")

        response = await client.get(
            "/users/autocomplete", params={"username": "pending"}
        )

        assert response.json()["users"] == []

    async def test_respects_limit(self, authed_client, create):
        client, _user = authed_client
        for suffix in range(3):
            await create(ActivatedUserFactory, username=f"limited{suffix}")

        response = await client.get(
            "/users/autocomplete", params={"username": "limited", "limit": 2}
        )

        assert len(response.json()["users"]) == 2


class TestGetUser:
    async def test_get_user_found(self, client, create):
        user = await create(ActivatedUserFactory)

        response = await client.get(f"/users/{user.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == user.id
        assert body["user"]["username"] == user.username

    async def test_get_user_not_found(self, client):
        response = await client.get("/users/999999")

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "user_not_found"

    async def test_get_user_defaults_when_no_meta_or_posts(self, client, create):
        user = await create(ActivatedUserFactory)

        response = await client.get(f"/users/{user.id}")

        assert response.status_code == 200
        body = response.json()["user"]
        assert body["avatar"] == user.avatar_url
        assert body["pronouns"] is None
        assert body["location"] is None
        assert body["showAge"] is False
        assert body["age"] is None
        assert body["postCount"] == 0
        assert body["communityPostCount"] == 0
        assert body["gamePostCount"] == 0

    async def test_get_user_includes_meta_fields(self, client, create, db_session):
        user = await create(ActivatedUserFactory)
        user_repository = UserRepository(db_session)
        await user_repository.update_user_meta(
            user,
            {
                UserMeta.MetaKeys.PRONOUNS: "they/them",
                UserMeta.MetaKeys.LOCATION: "Toronto",
                UserMeta.MetaKeys.BIRTHDAY: date(1990, 1, 1),
                UserMeta.MetaKeys.SHOW_AGE: True,
            },
        )

        response = await client.get(f"/users/{user.id}")

        body = response.json()["user"]
        assert body["pronouns"] == "they/them"
        assert body["location"] == "Toronto"
        assert body["showAge"] is True
        assert body["age"] is not None

    async def test_get_user_age_hidden_when_show_age_false(
        self, client, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        user_repository = UserRepository(db_session)
        await user_repository.update_user_meta(
            user,
            {
                UserMeta.MetaKeys.BIRTHDAY: date(1990, 1, 1),
                UserMeta.MetaKeys.SHOW_AGE: False,
            },
        )

        response = await client.get(f"/users/{user.id}")

        body = response.json()["user"]
        assert body["showAge"] is False
        assert body["age"] is None

    async def test_get_user_reflects_post_counts(self, client, create):
        user = await create(ActivatedUserFactory)
        thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread, author=user)

        response = await client.get(f"/users/{user.id}")

        body = response.json()["user"]
        assert body["postCount"] == 1
        assert body["communityPostCount"] == 1
        assert body["gamePostCount"] == 0


class TestGetUsers:
    async def test_requires_auth(self, client):
        response = await client.get("/users")

        assert response.status_code == 403

    async def test_requires_manage_users_permission(self, authed_client):
        client, _user = authed_client

        response = await client.get("/users")

        assert response.status_code == 403

    async def test_returns_lightweight_rows_for_manage_users_holder(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        listed = await create(ActivatedUserFactory, username="listperson")
        listed.last_activity = datetime.now(timezone.utc)
        await db_session.flush()

        response = await client.get("/users", params={"prefix": "listperson"})

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["page"] == 1
        row = body["users"][0]
        assert row["username"] == "listperson"
        assert {
            "id",
            "username",
            "avatar",
            "joinDate",
            "lastActivity",
            "activated",
        } <= set(row)
        assert row["activated"] is True
        # "full"-only fields stay out of the lightweight row
        for field in ("pronouns", "location", "age", "postCount", "activeGames"):
            assert field not in row

    async def test_prefix_filters_case_insensitively(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        await create(ActivatedUserFactory, username="Zeta")
        await create(ActivatedUserFactory, username="zebra")
        await create(ActivatedUserFactory, username="zoo")

        response = await client.get("/users", params={"prefix": "ZE"})

        assert {u["username"] for u in response.json()["users"]} == {"Zeta", "zebra"}

    async def test_sorted_by_creation_date(self, authed_client, db_session, create):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        # Created (and so id-ordered) alpha, bravo, charlie; join_date is set in
        # the reverse order so a plain id sort would not produce this result.
        now = datetime.now(timezone.utc)
        first = await create(ActivatedUserFactory, username="sortalpha")
        second = await create(ActivatedUserFactory, username="sortbravo")
        third = await create(ActivatedUserFactory, username="sortcharlie")
        first.join_date = now
        second.join_date = now - timedelta(days=1)
        third.join_date = now - timedelta(days=2)
        await db_session.flush()

        response = await client.get("/users", params={"prefix": "sort"})

        assert [u["username"] for u in response.json()["users"]] == [
            "sortcharlie",
            "sortbravo",
            "sortalpha",
        ]

    async def test_includes_unactivated_users_with_activation_flag(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        await create(ActivatedUserFactory, username="pendingactive")
        await create(UserFactory, username="pendingfella")

        response = await client.get("/users", params={"prefix": "pending"})

        body = response.json()
        assert body["count"] == 2
        activated_by_name = {u["username"]: u["activated"] for u in body["users"]}
        assert activated_by_name == {"pendingactive": True, "pendingfella": False}

    async def test_paginates_with_predefined_page_size(
        self, authed_client, db_session, create, monkeypatch
    ):
        monkeypatch.setattr(configs, "PAGINATE_PER_PAGE", 2)
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        for suffix in range(3):
            await create(ActivatedUserFactory, username=f"pageuser{suffix}")

        page_one = await client.get("/users", params={"prefix": "pageuser"})
        page_two = await client.get("/users", params={"prefix": "pageuser", "page": 2})

        assert page_one.json()["count"] == 3
        assert [u["username"] for u in page_one.json()["users"]] == [
            "pageuser0",
            "pageuser1",
        ]
        assert page_two.json()["page"] == 2
        assert [u["username"] for u in page_two.json()["users"]] == ["pageuser2"]

    async def test_banned_filter(self, authed_client, db_session, create):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        active = await create(ActivatedUserFactory, username="banfilteractive")
        banned = await create(ActivatedUserFactory, username="banfilterbanned")
        banned.banned = datetime.now(timezone.utc)
        await db_session.flush()

        both = await client.get("/users", params={"prefix": "banfilter"})
        only_banned = await client.get(
            "/users", params={"prefix": "banfilter", "banned": "true"}
        )
        only_active = await client.get(
            "/users", params={"prefix": "banfilter", "banned": "false"}
        )

        assert {u["username"] for u in both.json()["users"]} == {
            active.username,
            banned.username,
        }
        assert [u["id"] for u in only_banned.json()["users"]] == [banned.id]
        assert [u["id"] for u in only_active.json()["users"]] == [active.id]
        # the row carries the ban timestamp for banned users and omits it otherwise
        assert only_banned.json()["users"][0]["banned"] is not None
        assert "banned" not in only_active.json()["users"][0]

    async def test_full_includes_meta_for_admin(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.ADMIN)
        target = await create(ActivatedUserFactory, username="fulladmin")
        await UserRepository(db_session).update_user_meta(
            target,
            {
                UserMeta.MetaKeys.PRONOUNS: "they/them",
                UserMeta.MetaKeys.LOCATION: "Toronto",
                UserMeta.MetaKeys.BIRTHDAY: date(1990, 1, 1),
                UserMeta.MetaKeys.SHOW_AGE: True,
            },
        )

        response = await client.get(
            "/users", params={"prefix": "fulladmin", "full": "true"}
        )

        row = response.json()["users"][0]
        assert row["pronouns"] == "they/them"
        assert row["location"] == "Toronto"
        assert row["showAge"] is True
        assert row["age"] is not None

    async def test_full_downgraded_without_admin(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        target = await create(ActivatedUserFactory, username="fullnoadmin")
        await UserRepository(db_session).update_user_meta(
            target, {UserMeta.MetaKeys.PRONOUNS: "they/them"}
        )

        response = await client.get(
            "/users", params={"prefix": "fullnoadmin", "full": "true"}
        )

        assert response.status_code == 200
        row = response.json()["users"][0]
        assert "pronouns" not in row


class TestBanUser:
    async def test_requires_auth(self, client, create):
        target = await create(ActivatedUserFactory)

        response = await client.patch(f"/users/{target.id}/ban")

        assert response.status_code == 403

    async def test_requires_manage_users_permission(self, authed_client, create):
        client, _user = authed_client
        target = await create(ActivatedUserFactory)

        response = await client.patch(f"/users/{target.id}/ban")

        assert response.status_code == 403

    async def test_not_found(self, authed_client, db_session):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)

        response = await client.patch("/users/999999/ban")

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "user_not_found"

    async def test_cannot_ban_user_one(self, authed_client, db_session):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)

        response = await client.patch("/users/1/ban")

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "user_not_bannable"

    async def test_bans_unbanned_user(self, authed_client, db_session, create):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        target = await create(ActivatedUserFactory)

        response = await client.patch(f"/users/{target.id}/ban")

        assert response.status_code == 200
        assert response.json()["banned"] is not None
        await db_session.refresh(target)
        assert target.banned is not None

    async def test_unbans_banned_user(self, authed_client, db_session, create):
        client, user = authed_client
        await give_permission(db_session, user, Verbs.MANAGE_USERS)
        target = await create(ActivatedUserFactory)
        target.banned = datetime.now(timezone.utc)
        await db_session.flush()

        response = await client.patch(f"/users/{target.id}/ban")

        assert response.status_code == 200
        assert response.json()["banned"] is None
        await db_session.refresh(target)
        assert target.banned is None
