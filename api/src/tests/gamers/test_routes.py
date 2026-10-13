from datetime import datetime, timedelta, timezone

import pytest

from app.models import UserMeta
from tests.factories import ActivatedUserFactory, UserFactory

# Every gamer these tests make has "gmr" in the name, and each test searches for
# it: the requesting user is itself a (recently active) gamer and would otherwise
# show up in the results.
PREFIX = "gmr"


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def make_gamer(create, db_session):
    async def _make(
        name,
        *,
        last_activity=timedelta(days=1),
        lfg=False,
        join_date=None,
        **attrs,
    ):
        user = await create(ActivatedUserFactory, username=f"{PREFIX}{name}")
        user.last_activity = None if last_activity is None else _now() - last_activity
        if join_date is not None:
            user.join_date = join_date
        if lfg is not None:
            user.meta.append(
                UserMeta(key=UserMeta.MetaKeys.LOOKING_FOR_A_GAME.value, value=lfg)
            )
        for attr, value in attrs.items():
            setattr(user, attr, value)
        await db_session.flush()
        return user

    return _make


async def _get(client, **params):
    params.setdefault("search", PREFIX)
    response = await client.get("/gamers", params=params)
    assert response.status_code == 200
    return response.json()


def _names(body):
    return [gamer["username"].removeprefix(PREFIX) for gamer in body["gamers"]]


class TestGetGamers:
    async def test_gamer_shape(self, authed_client, make_gamer):
        client, _user = authed_client
        gamer = await make_gamer("a", last_activity=timedelta(hours=2), lfg=True)

        body = await _get(client)

        assert body["total"] == 1
        [result] = body["gamers"]
        assert result["id"] == gamer.id
        assert result["username"] == gamer.username
        assert result["avatar"] == gamer.avatar_url
        assert result["lfg"] is True
        assert result["online"] is False
        assert result["lastActivity"] is not None

    async def test_online_within_fifteen_minutes(self, authed_client, make_gamer):
        client, _user = authed_client
        await make_gamer("recent", last_activity=timedelta(minutes=14))
        await make_gamer("stale", last_activity=timedelta(minutes=16))

        body = await _get(client)

        online = {
            g["username"].removeprefix(PREFIX): g["online"] for g in body["gamers"]
        }
        assert online == {"recent": True, "stale": False}

    async def test_lfg_flag_false_when_meta_unset_or_false(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        await make_gamer("unset", lfg=None)
        await make_gamer("off", lfg=False)
        await make_gamer("on", lfg=True)

        body = await _get(client)

        flags = {g["username"].removeprefix(PREFIX): g["lfg"] for g in body["gamers"]}
        assert flags == {"unset": False, "off": False, "on": True}

    async def test_lfg_filter_only_returns_lfg_gamers(self, authed_client, make_gamer):
        client, _user = authed_client
        await make_gamer("on", lfg=True)
        await make_gamer("off", lfg=False)
        await make_gamer("unset", lfg=None)

        body = await _get(client, lfg="true")

        assert _names(body) == ["on"]
        assert body["total"] == 1

    async def test_search_is_case_insensitive_substring(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        await make_gamer("Alpha")
        await make_gamer("beta")

        body = await _get(client, search="GMRALPHA")
        assert _names(body) == ["Alpha"]

        body = await _get(client, search="ph")
        assert _names(body) == ["Alpha"]

    async def test_search_escapes_like_wildcards(self, authed_client, make_gamer):
        client, _user = authed_client
        await make_gamer("50%off")
        await make_gamer("50xoff")
        await make_gamer("a_b")
        await make_gamer("axb")
        await make_gamer("c\\d")
        await make_gamer("cxd")

        assert _names(await _get(client, search="50%")) == ["50%off"]
        assert _names(await _get(client, search="a_b")) == ["a_b"]
        assert _names(await _get(client, search="c\\d")) == ["c\\d"]


class TestGamerExclusions:
    async def test_excludes_unactivated_users(self, authed_client, create):
        client, _user = authed_client
        await create(UserFactory, username=f"{PREFIX}pending")

        body = await _get(client, include_inactive="true")

        assert body["total"] == 0

    async def test_excludes_banned_users(self, authed_client, make_gamer):
        client, _user = authed_client
        await make_gamer("ok")
        await make_gamer("banned", banned=_now())

        body = await _get(client, include_inactive="true")

        assert _names(body) == ["ok"]

    async def test_excludes_currently_suspended_users(self, authed_client, make_gamer):
        client, _user = authed_client
        await make_gamer("ok")
        await make_gamer("suspended", suspended_until=_now() + timedelta(days=1))

        body = await _get(client, include_inactive="true")

        assert _names(body) == ["ok"]

    async def test_includes_users_whose_suspension_has_lapsed(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        await make_gamer("lapsed", suspended_until=_now() - timedelta(days=1))

        body = await _get(client)

        assert _names(body) == ["lapsed"]

    async def test_inactive_users_hidden_by_default(self, authed_client, make_gamer):
        client, _user = authed_client
        await make_gamer("active", last_activity=timedelta(days=13))
        await make_gamer("stale", last_activity=timedelta(days=15))
        await make_gamer("never", last_activity=None)

        body = await _get(client)

        assert _names(body) == ["active"]
        assert body["total"] == 1

    async def test_include_inactive_returns_stale_and_never_active(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        await make_gamer("active", last_activity=timedelta(days=13))
        await make_gamer("stale", last_activity=timedelta(days=15))
        await make_gamer("never", last_activity=None)

        body = await _get(client, include_inactive="true")

        assert sorted(_names(body)) == ["active", "never", "stale"]
        assert body["total"] == 3
        never = next(g for g in body["gamers"] if g["username"].endswith("never"))
        assert never["lastActivity"] is None
        assert never["online"] is False

    async def test_lfg_and_inactive_filters_combine(self, authed_client, make_gamer):
        client, _user = authed_client
        await make_gamer("lfgactive", lfg=True)
        await make_gamer("lfgstale", lfg=True, last_activity=timedelta(days=30))
        await make_gamer("nolfg", lfg=False)

        assert _names(await _get(client, lfg="true")) == ["lfgactive"]
        body = await _get(client, lfg="true", include_inactive="true")
        assert sorted(_names(body)) == ["lfgactive", "lfgstale"]


class TestGamerSort:
    async def test_default_sort_is_name_case_insensitive(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        await make_gamer("charlie")
        await make_gamer("Alpha")
        await make_gamer("bravo")

        body = await _get(client)

        assert _names(body) == ["Alpha", "bravo", "charlie"]

    async def test_sort_newest_and_oldest_use_join_date(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        base = _now() - timedelta(days=100)
        await make_gamer("middle", join_date=base + timedelta(days=2))
        await make_gamer("first", join_date=base)
        await make_gamer("last", join_date=base + timedelta(days=5))

        assert _names(await _get(client, sort="newest")) == ["last", "middle", "first"]
        assert _names(await _get(client, sort="oldest")) == ["first", "middle", "last"]

    async def test_join_date_ties_break_on_id(self, authed_client, make_gamer):
        client, _user = authed_client
        joined = _now() - timedelta(days=10)
        low = await make_gamer("low", join_date=joined)
        high = await make_gamer("high", join_date=joined)
        assert low.id < high.id

        assert _names(await _get(client, sort="oldest")) == ["low", "high"]
        assert _names(await _get(client, sort="newest")) == ["high", "low"]

    async def test_online_gamers_are_not_floated_to_the_top(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        await make_gamer("a", last_activity=timedelta(days=2))
        await make_gamer("b", last_activity=timedelta(minutes=1))

        body = await _get(client)

        assert _names(body) == ["a", "b"]


class TestGamerPagination:
    async def test_pages_of_25_with_full_total(self, authed_client, make_gamer):
        client, _user = authed_client
        for i in range(27):
            await make_gamer(f"{i:02d}")

        first = await _get(client)
        second = await _get(client, page=2)
        third = await _get(client, page=3)

        assert first["total"] == second["total"] == third["total"] == 27
        assert _names(first) == [f"{i:02d}" for i in range(25)]
        assert _names(second) == ["25", "26"]
        assert third["gamers"] == []

    async def test_page_below_one_is_treated_as_first_page(
        self, authed_client, make_gamer
    ):
        client, _user = authed_client
        await make_gamer("a")

        body = await _get(client, page=0)

        assert _names(body) == ["a"]
