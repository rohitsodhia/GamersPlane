import pytest
from sqlalchemy import func, select

from app.models import Post, PostDraw, PostRoll, RolePermission, Thread
from app.repositories import DeckRepository
from tests.factories import PostFactory, ThreadFactory, prose_doc
from tests.game_forum import allow_drawing, make_game_forum, make_user_with

Verbs = RolePermission.ValidPermissions

PLAYER_VERBS = (
    Verbs.FORUM_READ,
    Verbs.FORUM_WRITE,
    Verbs.FORUM_EDIT,
    Verbs.FORUM_ADD_ROLLS,
    Verbs.FORUM_ADD_DRAWS,
)


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def thread(create, world):
    return await create(
        ThreadFactory,
        forum=world.forum,
        options=Thread.Options(allow_rolls=True, allow_draws=True),
    )


@pytest.fixture
async def author(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


@pytest.fixture
async def moderator(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, Verbs.FORUM_MODERATE)


@pytest.fixture
async def other(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, Verbs.FORUM_READ)


def as_anonymous(client):
    client.headers.pop("Authorization", None)


def roll_payload(**overrides):
    payload = {"type": "basic", "roll": "2d6+1", "reason": "Attack"}
    payload.update(overrides)
    return payload


def draw_payload(deck, **overrides):
    payload = {"deck_id": deck.id, "count": 2, "reason": "Fortune"}
    payload.update(overrides)
    return payload


def post_payload(thread, **overrides):
    payload = {"thread_id": thread.id, "title": "A post", "body": prose_doc("Body")}
    payload.update(overrides)
    return payload


def edit_payload(**overrides):
    payload = {"title": "Edited", "body": prose_doc("Edited body")}
    payload.update(overrides)
    return payload


async def read_first_post(client, thread):
    response = await client.get("/posts", params={"thread_id": thread.id})
    assert response.status_code == 200
    return response.json()["posts"][0]


async def count(db_session, model):
    return await db_session.scalar(select(func.count()).select_from(model))


class TestCreatePostWithRolls:
    async def test_roll_is_stored_with_options_and_result(
        self, auth_as, thread, author, db_session
    ):
        client = auth_as(author)

        response = await client.post(
            "/posts",
            json=post_payload(
                thread,
                rolls=[roll_payload(options={"reroll_aces": True}, hide_dice=True)],
            ),
        )

        assert response.status_code == 200
        roll = await db_session.scalar(select(PostRoll))
        assert roll.post_id == response.json()["id"]
        assert roll.type == "basic"
        assert roll.reason == "Attack"
        assert roll.input == "2d6+1"
        assert roll.options == {"reroll_aces": True}
        assert roll.hide_dice is True
        assert roll.hide_reason is False
        assert roll.result["groups"][0]["expression"] == "2d6+1"
        assert roll.result["total"] == roll.result["groups"][0]["total"]

    @pytest.mark.parametrize(
        ("system", "roll", "options", "stored_options"),
        [
            ("basic", "1d20", {}, {"reroll_aces": False}),
            ("fate", "4", {"modifier": 2, "reroll_aces": True}, {"modifier": 2}),
            ("fengshui", "10", {"roll_type": "closed"}, {"roll_type": "closed"}),
            ("starwarsffg", "a p d", {"modifier": 3}, {}),
        ],
    )
    async def test_each_system_rolls_and_keeps_only_its_options(
        self, auth_as, thread, author, db_session, system, roll, options, stored_options
    ):
        client = auth_as(author)

        response = await client.post(
            "/posts",
            json=post_payload(
                thread, rolls=[roll_payload(type=system, roll=roll, options=options)]
            ),
        )

        assert response.status_code == 200
        stored = await db_session.scalar(select(PostRoll))
        assert stored.options == stored_options

    async def test_roll_rejected_when_thread_disallows_rolls(
        self, auth_as, create, world, author
    ):
        closed = await create(ThreadFactory, forum=world.forum)
        client = auth_as(author)

        response = await client.post(
            "/posts", json=post_payload(closed, rolls=[roll_payload()])
        )

        assert response.status_code == 403

    async def test_roll_rejected_without_add_rolls_permission(
        self, auth_as, create, db_session, world, thread
    ):
        user = await make_user_with(
            create, db_session, world.forum, Verbs.FORUM_READ, Verbs.FORUM_WRITE
        )
        client = auth_as(user)

        response = await client.post(
            "/posts", json=post_payload(thread, rolls=[roll_payload()])
        )

        assert response.status_code == 403

    @pytest.mark.parametrize(
        "bad_roll",
        [
            roll_payload(roll="abc"),
            roll_payload(roll="   "),
            roll_payload(type="fate", roll="lots"),
            roll_payload(type="starwarsffg", roll="zzz"),
            roll_payload(type="fengshui", roll="ten"),
        ],
    )
    async def test_unrollable_input_returns_400(
        self, auth_as, thread, author, bad_roll
    ):
        client = auth_as(author)

        response = await client.post(
            "/posts", json=post_payload(thread, rolls=[bad_roll])
        )

        assert response.status_code == 400

    async def test_invalid_roll_leaves_no_post_or_other_rolls_behind(
        self, auth_as, thread, author, db_session
    ):
        client = auth_as(author)

        response = await client.post(
            "/posts",
            json=post_payload(
                thread, rolls=[roll_payload(), roll_payload(roll="nonsense")]
            ),
        )

        assert response.status_code == 400
        assert await count(db_session, PostRoll) == 0
        assert await count(db_session, Post) == 0


class TestRollRedactionByViewer:
    @pytest.fixture
    async def post(self, auth_as, thread, author):
        client = auth_as(author)
        response = await client.post(
            "/posts",
            json=post_payload(
                thread,
                rolls=[
                    roll_payload(hide_reason=True, hide_dice=True, hide_result=True)
                ],
            ),
        )
        return response.json()["id"]

    @pytest.mark.parametrize("viewer", ["author", "moderator"])
    async def test_author_and_moderator_see_a_fully_hidden_roll(
        self, auth_as, thread, post, author, moderator, viewer
    ):
        client = auth_as({"author": author, "moderator": moderator}[viewer])

        roll = (await read_first_post(client, thread))["rolls"][0]

        assert roll["reason"] == "Attack"
        assert roll["input"] == "2d6+1"
        assert roll["result"]["total"] is not None
        assert roll["summary"] is None
        assert (roll["hide_reason"], roll["hide_dice"], roll["hide_result"]) == (
            True,
            True,
            True,
        )

    @pytest.mark.parametrize("viewer", ["other", "anonymous"])
    async def test_other_viewers_get_a_redacted_roll(
        self, auth_as, thread, post, other, viewer
    ):
        client = auth_as(other)
        if viewer == "anonymous":
            as_anonymous(client)

        roll = (await read_first_post(client, thread))["rolls"][0]

        assert roll["reason"] is None
        assert roll["input"] is None
        assert roll["options"] is None
        assert roll["result"] is None
        assert roll["summary"] is None
        assert roll["hide_reason"] is True

    async def test_get_post_redacts_the_same_way(self, auth_as, post, author, other):
        client = auth_as(other)

        roll = (await client.get(f"/posts/{post}")).json()["rolls"][0]

        assert roll["result"] is None
        assert roll["reason"] is None

        client = auth_as(author)
        roll = (await client.get(f"/posts/{post}")).json()["rolls"][0]

        assert roll["result"] is not None


class TestCreatePostWithDraws:
    async def test_draw_takes_cards_in_order_and_advances_the_deck(
        self, auth_as, world, thread, author, db_session
    ):
        await allow_drawing(db_session, author, world.deck)
        order = list(world.deck.order)
        client = auth_as(author)

        first = await client.post(
            "/posts", json=post_payload(thread, draws=[draw_payload(world.deck)])
        )
        second = await client.post(
            "/posts",
            json=post_payload(thread, draws=[draw_payload(world.deck, count=3)]),
        )

        assert first.status_code == second.status_code == 200
        draws = list(await db_session.scalars(select(PostDraw).order_by(PostDraw.id)))
        assert draws[0].cards == order[:2]
        assert draws[1].cards == order[2:5]
        assert draws[0].revealed == [False, False]
        assert draws[0].deck_label == "Fate Deck"
        assert draws[0].deck_type == world.deck.type_id
        await db_session.refresh(world.deck)
        assert world.deck.position == 5

    async def test_gm_can_draw_without_a_deck_permission(
        self, auth_as, world, thread, db_session
    ):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=post_payload(thread, draws=[draw_payload(world.deck)])
        )

        assert response.status_code == 200
        assert await count(db_session, PostDraw) == 1

    async def test_player_without_deck_permission_is_forbidden(
        self, auth_as, world, thread, author, db_session
    ):
        client = auth_as(author)

        response = await client.post(
            "/posts", json=post_payload(thread, draws=[draw_payload(world.deck)])
        )

        assert response.status_code == 403
        await db_session.refresh(world.deck)
        assert world.deck.position == 0

    async def test_deck_from_another_game_returns_404(
        self, auth_as, world, thread, author, db_session
    ):
        other_game = await world.make_game("Other Campaign")
        await allow_drawing(db_session, author, other_game.deck)
        client = auth_as(author)

        response = await client.post(
            "/posts",
            json=post_payload(thread, draws=[draw_payload(other_game.deck)]),
        )

        assert response.status_code == 404

    async def test_draw_in_a_non_game_forum_is_forbidden(
        self, auth_as, create, db_session, world
    ):
        # Outside every game, so the draw is refused before any deck is looked at.
        site_thread = await create(
            ThreadFactory, options=Thread.Options(allow_draws=True)
        )
        user = await make_user_with(
            create, db_session, site_thread.forum, *PLAYER_VERBS
        )
        client = auth_as(user)

        response = await client.post(
            "/posts", json=post_payload(site_thread, draws=[draw_payload(world.deck)])
        )

        assert response.status_code == 403

    async def test_draw_rejected_when_thread_disallows_draws(
        self, auth_as, create, world
    ):
        closed = await create(ThreadFactory, forum=world.forum)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=post_payload(closed, draws=[draw_payload(world.deck)])
        )

        assert response.status_code == 403

    async def test_draw_rejected_without_add_draws_permission(
        self, auth_as, create, db_session, world, thread
    ):
        user = await make_user_with(
            create, db_session, world.forum, Verbs.FORUM_READ, Verbs.FORUM_WRITE
        )
        await allow_drawing(db_session, user, world.deck)
        client = auth_as(user)

        response = await client.post(
            "/posts", json=post_payload(thread, draws=[draw_payload(world.deck)])
        )

        assert response.status_code == 403

    async def test_draws_from_two_decks_in_one_post(
        self, auth_as, world, thread, db_session
    ):
        tarot = await DeckRepository(db_session, principal=world.gm).create(
            game_id=world.game.id,
            label="Tarot",
            type=world.deck.type_id,
            permissions=[],
        )
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=post_payload(
                thread,
                draws=[
                    draw_payload(tarot, count=1),
                    draw_payload(world.deck, count=2),
                ],
            ),
        )

        assert response.status_code == 200
        draws = list(await db_session.scalars(select(PostDraw).order_by(PostDraw.id)))
        assert [(d.deck_id, d.cards) for d in draws] == [
            (tarot.id, tarot.order[:1]),
            (world.deck.id, world.deck.order[:2]),
        ]
        await db_session.refresh(tarot)
        await db_session.refresh(world.deck)
        assert (tarot.position, world.deck.position) == (1, 2)

    async def test_drawing_every_remaining_card_is_allowed(
        self, auth_as, world, thread, db_session
    ):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=post_payload(thread, draws=[draw_payload(world.deck, count=52)]),
        )

        assert response.status_code == 200
        await db_session.refresh(world.deck)
        assert world.deck.position == 52

    async def test_overdrawing_returns_400_and_leaves_the_deck_alone(
        self, auth_as, world, thread, db_session
    ):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=post_payload(thread, draws=[draw_payload(world.deck, count=53)]),
        )

        assert response.status_code == 400
        await db_session.refresh(world.deck)
        assert world.deck.position == 0

    async def test_same_deck_twice_in_one_request_returns_400(
        self, auth_as, world, thread
    ):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=post_payload(
                thread,
                draws=[
                    draw_payload(world.deck, count=1),
                    draw_payload(world.deck, count=1),
                ],
            ),
        )

        assert response.status_code == 400

    async def test_whitespace_only_reason_returns_400(self, auth_as, world, thread):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=post_payload(thread, draws=[draw_payload(world.deck, reason="  ")]),
        )

        assert response.status_code == 400

    async def test_failed_roll_does_not_advance_a_valid_draw(
        self, auth_as, world, thread, db_session
    ):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=post_payload(
                thread,
                rolls=[roll_payload(roll="nonsense")],
                draws=[draw_payload(world.deck)],
            ),
        )

        assert response.status_code == 400
        await db_session.refresh(world.deck)
        assert world.deck.position == 0
        assert await count(db_session, PostDraw) == 0


class TestDrawVisibility:
    @pytest.fixture
    async def drawn_post(self, auth_as, world, thread, author, db_session):
        await allow_drawing(db_session, author, world.deck)
        client = auth_as(author)
        response = await client.post(
            "/posts", json=post_payload(thread, draws=[draw_payload(world.deck)])
        )
        return response.json()["id"]

    async def test_author_sees_every_card(
        self, auth_as, world, thread, author, drawn_post
    ):
        client = auth_as(author)

        draw = (await read_first_post(client, thread))["draws"][0]

        assert draw["cards"] == world.deck.order[:2]
        assert draw["revealed"] == [False, False]

    @pytest.mark.parametrize("viewer", ["gm", "moderator", "other", "anonymous"])
    async def test_everyone_else_sees_hidden_cards_as_null(
        self, auth_as, world, thread, moderator, other, drawn_post, viewer
    ):
        client = auth_as({"gm": world.gm, "moderator": moderator}.get(viewer, other))
        if viewer == "anonymous":
            as_anonymous(client)

        draw = (await read_first_post(client, thread))["draws"][0]

        assert draw["cards"] == [None, None]
        assert draw["revealed"] == [False, False]
        assert draw["deck_label"] == "Fate Deck"


class TestToggleCard:
    @pytest.fixture
    async def drawn_post(self, auth_as, world, thread, author, db_session):
        await allow_drawing(db_session, author, world.deck)
        client = auth_as(author)
        response = await client.post(
            "/posts", json=post_payload(thread, draws=[draw_payload(world.deck)])
        )
        post_id = response.json()["id"]
        draw = await db_session.scalar(select(PostDraw))
        return post_id, draw

    def url(self, post_id, draw, index):
        return f"/posts/{post_id}/draws/{draw.id}/cards/{index}/toggle"

    async def test_author_reveals_and_rehides_a_card(
        self, auth_as, world, thread, author, other, drawn_post
    ):
        post_id, draw = drawn_post
        client = auth_as(author)

        revealed = await client.post(self.url(post_id, draw, 1))

        assert revealed.status_code == 200
        assert revealed.json()["revealed"] == [False, True]
        assert revealed.json()["cards"] == world.deck.order[:2]
        client = auth_as(other)
        seen = (await read_first_post(client, thread))["draws"][0]
        assert seen["cards"] == [None, world.deck.order[1]]

        client = auth_as(author)
        hidden = await client.post(self.url(post_id, draw, 1))

        assert hidden.json()["revealed"] == [False, False]
        client = auth_as(other)
        seen = (await read_first_post(client, thread))["draws"][0]
        assert seen["cards"] == [None, None]

    @pytest.mark.parametrize("viewer", ["gm", "moderator", "other"])
    async def test_only_the_author_may_toggle(
        self, auth_as, world, moderator, other, drawn_post, db_session, viewer
    ):
        post_id, draw = drawn_post
        client = auth_as({"gm": world.gm, "moderator": moderator}.get(viewer, other))

        response = await client.post(self.url(post_id, draw, 0))

        assert response.status_code == 403
        await db_session.refresh(draw)
        assert draw.revealed == [False, False]

    async def test_author_cannot_toggle_in_a_locked_thread(
        self, auth_as, thread, author, drawn_post, db_session
    ):
        post_id, draw = drawn_post
        thread.options = Thread.Options(allow_draws=True, locked=True)
        await db_session.flush()
        client = auth_as(author)

        response = await client.post(self.url(post_id, draw, 0))

        assert response.status_code == 403
        await db_session.refresh(draw)
        assert draw.revealed == [False, False]

    async def test_moderator_author_can_toggle_in_a_locked_thread(
        self, auth_as, create, world, thread, db_session
    ):
        mod_author = await make_user_with(
            create, db_session, world.forum, *PLAYER_VERBS, Verbs.FORUM_MODERATE
        )
        await allow_drawing(db_session, mod_author, world.deck)
        client = auth_as(mod_author)
        response = await client.post(
            "/posts", json=post_payload(thread, draws=[draw_payload(world.deck)])
        )
        draw = await db_session.scalar(select(PostDraw))
        thread.options = Thread.Options(allow_draws=True, locked=True)
        await db_session.flush()

        toggled = await client.post(self.url(response.json()["id"], draw, 0))

        assert toggled.status_code == 200
        assert toggled.json()["revealed"] == [True, False]

    @pytest.mark.parametrize("index", [2, -1])
    async def test_index_out_of_range_returns_400(
        self, auth_as, author, drawn_post, index
    ):
        post_id, draw = drawn_post
        client = auth_as(author)

        response = await client.post(self.url(post_id, draw, index))

        assert response.status_code == 400

    async def test_draw_from_another_post_returns_404(
        self, auth_as, create, thread, author, drawn_post
    ):
        _post_id, draw = drawn_post
        other_post = await create(PostFactory, thread=thread, author=author)
        client = auth_as(author)

        response = await client.post(self.url(other_post.id, draw, 0))

        assert response.status_code == 404

    async def test_unknown_post_returns_404(self, auth_as, author, drawn_post):
        _post_id, draw = drawn_post
        client = auth_as(author)

        response = await client.post(self.url(999999, draw, 0))

        assert response.status_code == 404


class TestEditPostAttachments:
    @pytest.fixture
    async def rolled_post(self, auth_as, thread, author):
        client = auth_as(author)
        response = await client.post(
            "/posts", json=post_payload(thread, rolls=[roll_payload()])
        )
        return response.json()["id"]

    async def test_editing_the_body_leaves_rolls_untouched(
        self, auth_as, author, rolled_post, db_session
    ):
        before = await db_session.scalar(select(PostRoll))
        snapshot = (before.id, before.result, before.input, before.reason)
        client = auth_as(author)

        response = await client.patch(
            f"/posts/{rolled_post}", json=edit_payload(title="Rewritten")
        )

        assert response.status_code == 200
        rolls = list(await db_session.scalars(select(PostRoll)))
        assert [(r.id, r.result, r.input, r.reason) for r in rolls] == [snapshot]

    async def test_edit_adds_new_rolls_alongside_existing_ones(
        self, auth_as, author, rolled_post, thread
    ):
        client = auth_as(author)

        response = await client.patch(
            f"/posts/{rolled_post}",
            json=edit_payload(rolls=[roll_payload(roll="1d20", reason="Second")]),
        )

        assert response.status_code == 200
        rolls = (await read_first_post(client, thread))["rolls"]
        assert [r["reason"] for r in rolls] == ["Attack", "Second"]

    async def test_edit_adds_a_draw(
        self, auth_as, world, thread, author, rolled_post, db_session
    ):
        await allow_drawing(db_session, author, world.deck)
        client = auth_as(author)

        response = await client.patch(
            f"/posts/{rolled_post}",
            json=edit_payload(draws=[draw_payload(world.deck, count=1)]),
        )

        assert response.status_code == 200
        draws = (await read_first_post(client, thread))["draws"]
        assert draws[0]["cards"] == world.deck.order[:1]

    async def test_edit_adding_a_roll_is_checked_against_thread_options(
        self, auth_as, create, world, author
    ):
        closed = await create(ThreadFactory, forum=world.forum)
        post = await create(PostFactory, thread=closed, author=author)
        client = auth_as(author)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_payload(rolls=[roll_payload()])
        )

        assert response.status_code == 403

    async def test_moderator_cannot_add_rolls_to_someone_elses_post(
        self, auth_as, moderator, rolled_post
    ):
        client = auth_as(moderator)

        response = await client.patch(
            f"/posts/{rolled_post}", json=edit_payload(rolls=[roll_payload()])
        )

        assert response.status_code == 403

    @pytest.mark.parametrize("editor", ["author", "moderator"])
    async def test_author_and_moderator_can_change_visibility(
        self, auth_as, author, moderator, rolled_post, db_session, editor
    ):
        roll = await db_session.scalar(select(PostRoll))
        client = auth_as({"author": author, "moderator": moderator}[editor])

        response = await client.patch(
            f"/posts/{rolled_post}",
            json=edit_payload(
                roll_visibility=[
                    {
                        "id": roll.id,
                        "hide_reason": True,
                        "hide_dice": False,
                        "hide_result": True,
                    }
                ]
            ),
        )

        assert response.status_code == 200
        await db_session.refresh(roll)
        assert (roll.hide_reason, roll.hide_dice, roll.hide_result) == (
            True,
            False,
            True,
        )

    async def test_other_user_cannot_change_visibility(
        self, auth_as, other, rolled_post, db_session
    ):
        roll = await db_session.scalar(select(PostRoll))
        client = auth_as(other)

        response = await client.patch(
            f"/posts/{rolled_post}",
            json=edit_payload(
                roll_visibility=[
                    {
                        "id": roll.id,
                        "hide_reason": True,
                        "hide_dice": True,
                        "hide_result": True,
                    }
                ]
            ),
        )

        assert response.status_code == 403
        await db_session.refresh(roll)
        assert roll.hide_result is False

    async def test_visibility_for_a_roll_on_another_post_returns_400(
        self, auth_as, thread, author, rolled_post, db_session
    ):
        client = auth_as(author)
        other_post = await client.post(
            "/posts", json=post_payload(thread, rolls=[roll_payload()])
        )
        foreign = await db_session.scalar(
            select(PostRoll).where(PostRoll.post_id == other_post.json()["id"])
        )

        response = await client.patch(
            f"/posts/{rolled_post}",
            json=edit_payload(
                roll_visibility=[
                    {
                        "id": foreign.id,
                        "hide_reason": True,
                        "hide_dice": True,
                        "hide_result": True,
                    }
                ]
            ),
        )

        assert response.status_code == 400
        await db_session.refresh(foreign)
        assert foreign.hide_result is False

    async def test_visibility_listing_a_roll_twice_returns_400(
        self, auth_as, author, rolled_post, db_session
    ):
        roll = await db_session.scalar(select(PostRoll))
        change = {
            "id": roll.id,
            "hide_reason": True,
            "hide_dice": False,
            "hide_result": False,
        }
        client = auth_as(author)

        response = await client.patch(
            f"/posts/{rolled_post}",
            json=edit_payload(roll_visibility=[change, change]),
        )

        assert response.status_code == 400
