import pydantic
import pytest
from sqlalchemy import func, select

from app.models import Poll, PollOption, PollVote, RolePermission, Thread
from app.repositories import PollRepository
from app.threads.poll_schemas import PollInput
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ForumFactory,
    PostFactory,
    RoleFactory,
    ThreadFactory,
    UserFactory,
    prose_doc,
)

Verbs = RolePermission.ValidPermissions


async def grant(db_session, user, forum, *verbs):
    """Give ``user`` a role holding ``verbs`` on ``forum``."""
    role = RoleFactory.build()
    db_session.add(role)
    for verb in verbs:
        role.grant(verb, scope_type=RolePermission.ScopeTypes.FORUM, scope_id=forum.id)
    role.users.append(user)
    await db_session.flush()


def poll_payload(**overrides):
    payload = {
        "question": "Best snack?",
        "options_per_user": 1,
        "allow_revoting": False,
        "options": [{"text": "Apples"}, {"text": "Bananas"}, {"text": "Cherries"}],
    }
    payload.update(overrides)
    return payload


async def make_thread(create, db_session, author, **thread_kwargs):
    """A thread whose first post is by ``author``."""
    thread = await create(ThreadFactory, **thread_kwargs)
    first_post = await create(PostFactory, thread=thread, author=author)
    thread.first_post_id = first_post.id
    thread.last_post_id = first_post.id
    thread.last_post_at = first_post.published_at
    thread.post_count = 1
    await db_session.flush()
    return thread, first_post


async def make_poll(db_session, thread, **overrides):
    """Add a poll to ``thread``, returning its options in order."""
    repository = PollRepository(db_session, principal=None)
    await repository.create(thread.id, PollInput(**poll_payload(**overrides)))
    return await repository.get_options(thread.id)


async def cast_votes(db_session, thread, user, option_ids):
    await PollRepository(db_session, principal=user).replace_votes(
        thread.id, user.id, option_ids
    )


async def count(db_session, model):
    return await db_session.scalar(select(func.count()).select_from(model))


def edit_payload(**overrides):
    payload = {"title": "Edited", "body": prose_doc("Edited body")}
    payload.update(overrides)
    return payload


class TestPollInput:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"question": "   "},
            {"question": "x" * 201},
            {"options": [{"text": "Only one"}]},
            {"options": [{"text": f"Option {n}"} for n in range(26)]},
            {"options": [{"text": "A"}, {"text": "  "}]},
            {"options": [{"text": "A" * 201}, {"text": "B"}]},
            {"options": [{"text": "Same"}, {"text": " same "}]},
            {"options": [{"id": 4, "text": "A"}, {"id": 4, "text": "B"}]},
            {"options_per_user": 0},
            {"options_per_user": 4},
        ],
        ids=[
            "blank question",
            "long question",
            "one option",
            "too many options",
            "blank option",
            "long option",
            "duplicate text",
            "duplicate id",
            "zero per user",
            "per user above option count",
        ],
    )
    def test_invalid_input_is_rejected(self, overrides):
        with pytest.raises(pydantic.ValidationError):
            PollInput(**poll_payload(**overrides))

    def test_text_is_trimmed(self):
        poll = PollInput(
            **poll_payload(question="  Q?  ", options=[{"text": " A "}, {"text": "B"}])
        )

        assert poll.question == "Q?"
        assert [option.text for option in poll.options] == ["A", "B"]


class TestCreateThreadWithPoll:
    async def test_creates_poll_with_options_in_order(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await grant(db_session, user, forum, Verbs.FORUM_ADD_POLL)

        response = await client.post(
            "/threads",
            json={
                "forum_id": forum.id,
                "title": "Hello",
                "body": prose_doc("Hi"),
                "poll": poll_payload(options_per_user=2),
            },
        )

        assert response.status_code == 200
        thread_id = response.json()["id"]
        poll = await db_session.get(Poll, thread_id)
        assert (poll.question, poll.options_per_user, poll.allow_revoting) == (
            "Best snack?",
            2,
            False,
        )
        options = await PollRepository(db_session, principal=user).get_options(
            thread_id
        )
        assert [(o.text, o.position) for o in options] == [
            ("Apples", 0),
            ("Bananas", 1),
            ("Cherries", 2),
        ]

    async def test_without_add_poll_returns_403(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.post(
            "/threads",
            json={
                "forum_id": forum.id,
                "title": "Hello",
                "body": prose_doc("Hi"),
                "poll": poll_payload(),
            },
        )

        assert response.status_code == 403
        assert await count(db_session, Poll) == 0

    async def test_moderator_can_add_a_poll(self, authed_client, create, db_session):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await grant(db_session, user, forum, Verbs.FORUM_MODERATE)

        response = await client.post(
            "/threads",
            json={
                "forum_id": forum.id,
                "title": "Hello",
                "body": prose_doc("Hi"),
                "poll": poll_payload(),
            },
        )

        assert response.status_code == 200

    async def test_option_ids_on_create_return_400(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await grant(db_session, user, forum, Verbs.FORUM_ADD_POLL)

        response = await client.post(
            "/threads",
            json={
                "forum_id": forum.id,
                "title": "Hello",
                "body": prose_doc("Hi"),
                "poll": poll_payload(options=[{"id": 1, "text": "A"}, {"text": "B"}]),
            },
        )

        assert response.status_code == 400
        assert await count(db_session, Poll) == 0


class TestEditPostPoll:
    async def setup_thread(self, authed_client, create, db_session, with_poll=True):
        client, user = authed_client
        thread, first_post = await make_thread(create, db_session, user)
        await grant(db_session, user, thread.forum, Verbs.FORUM_ADD_POLL)
        options = await make_poll(db_session, thread) if with_poll else []
        return client, user, thread, first_post, options

    async def test_absent_poll_is_left_alone(self, authed_client, create, db_session):
        client, _user, thread, first_post, _options = await self.setup_thread(
            authed_client, create, db_session
        )

        response = await client.patch(f"/posts/{first_post.id}", json=edit_payload())

        assert response.status_code == 200
        assert await db_session.get(Poll, thread.id) is not None

    async def test_null_removes_the_poll_and_its_votes(
        self, authed_client, create, db_session
    ):
        client, user, thread, first_post, options = await self.setup_thread(
            authed_client, create, db_session
        )
        await cast_votes(db_session, thread, user, [options[0].id])

        response = await client.patch(
            f"/posts/{first_post.id}", json=edit_payload(poll=None)
        )

        assert response.status_code == 200
        assert await count(db_session, Poll) == 0
        assert await count(db_session, PollOption) == 0
        assert await count(db_session, PollVote) == 0

    async def test_null_without_a_poll_is_a_no_op(
        self, authed_client, create, db_session
    ):
        client, _user, _thread, first_post, _options = await self.setup_thread(
            authed_client, create, db_session, with_poll=False
        )

        response = await client.patch(
            f"/posts/{first_post.id}", json=edit_payload(poll=None)
        )

        assert response.status_code == 200

    async def test_object_creates_a_poll_when_there_is_none(
        self, authed_client, create, db_session
    ):
        client, _user, thread, first_post, _options = await self.setup_thread(
            authed_client, create, db_session, with_poll=False
        )

        response = await client.patch(
            f"/posts/{first_post.id}", json=edit_payload(poll=poll_payload())
        )

        assert response.status_code == 200
        assert (await db_session.get(Poll, thread.id)).question == "Best snack?"

    async def test_update_keeps_votes_on_kept_options_and_drops_the_rest(
        self, authed_client, create, db_session
    ):
        client, user, thread, first_post, options = await self.setup_thread(
            authed_client, create, db_session
        )
        apples, bananas, cherries = options
        voter = await create(UserFactory)
        await cast_votes(db_session, thread, user, [apples.id])
        await cast_votes(db_session, thread, voter, [cherries.id])

        # Reorder, rename Apples, drop Cherries, add Dates.
        response = await client.patch(
            f"/posts/{first_post.id}",
            json=edit_payload(
                poll=poll_payload(
                    question="Better snack?",
                    allow_revoting=True,
                    options=[
                        {"id": bananas.id, "text": "Bananas"},
                        {"id": apples.id, "text": "Green apples"},
                        {"text": "Dates"},
                    ],
                )
            ),
        )

        assert response.status_code == 200
        poll = await db_session.get(Poll, thread.id)
        assert (poll.question, poll.allow_revoting) == ("Better snack?", True)
        new_options = await PollRepository(db_session, principal=user).get_options(
            thread.id
        )
        assert [(o.text, o.position) for o in new_options] == [
            ("Bananas", 0),
            ("Green apples", 1),
            ("Dates", 2),
        ]
        assert new_options[1].id == apples.id
        votes = (await db_session.scalars(select(PollVote))).all()
        assert [(v.user_id, v.option_id) for v in votes] == [(user.id, apples.id)]

    async def test_option_from_another_poll_returns_400(
        self, authed_client, create, db_session
    ):
        client, _user, _thread, first_post, _options = await self.setup_thread(
            authed_client, create, db_session
        )
        other_thread, _ = await make_thread(
            create, db_session, await create(UserFactory)
        )
        [foreign, *_rest] = await make_poll(db_session, other_thread)

        response = await client.patch(
            f"/posts/{first_post.id}",
            json=edit_payload(
                poll=poll_payload(
                    options=[{"id": foreign.id, "text": "A"}, {"text": "B"}]
                )
            ),
        )

        assert response.status_code == 400
        assert await db_session.get(PollOption, foreign.id) is not None

    async def test_removing_a_poll_without_add_poll_returns_403(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, first_post = await make_thread(create, db_session, user)
        await make_poll(db_session, thread)

        response = await client.patch(
            f"/posts/{first_post.id}", json=edit_payload(poll=None)
        )

        assert response.status_code == 403
        assert await count(db_session, Poll) == 1

    async def test_poll_on_a_reply_returns_400(self, authed_client, create, db_session):
        client, user, thread, _first_post, _options = await self.setup_thread(
            authed_client, create, db_session
        )
        reply = await create(PostFactory, thread=thread, author=user)

        response = await client.patch(
            f"/posts/{reply.id}", json=edit_payload(poll=poll_payload())
        )

        assert response.status_code == 400

    async def test_without_add_poll_returns_403_and_keeps_the_post(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, first_post = await make_thread(create, db_session, user)
        original_title = first_post.title

        response = await client.patch(
            f"/posts/{first_post.id}", json=edit_payload(poll=poll_payload())
        )

        assert response.status_code == 403
        await db_session.refresh(first_post)
        assert first_post.title == original_title
        assert await count(db_session, Poll) == 0

    async def test_options_per_user_below_current_votes_returns_400(
        self, authed_client, create, db_session
    ):
        client, _user, thread, first_post, options = await self.setup_thread(
            authed_client, create, db_session
        )
        voter = await create(UserFactory)
        # The poll was made with one pick each; store a voter with two directly.
        poll = await db_session.get(Poll, thread.id)
        poll.options_per_user = 2
        await cast_votes(db_session, thread, voter, [options[0].id, options[1].id])

        response = await client.patch(
            f"/posts/{first_post.id}",
            json=edit_payload(
                poll=poll_payload(
                    options_per_user=1,
                    options=[{"id": o.id, "text": o.text} for o in options],
                )
            ),
        )

        assert response.status_code == 400
        await db_session.refresh(poll)
        assert poll.options_per_user == 2

    async def test_votes_on_removed_options_dont_block_lowering_options_per_user(
        self, authed_client, create, db_session
    ):
        client, _user, thread, first_post, options = await self.setup_thread(
            authed_client, create, db_session
        )
        voter = await create(UserFactory)
        poll = await db_session.get(Poll, thread.id)
        poll.options_per_user = 2
        await cast_votes(db_session, thread, voter, [options[0].id, options[1].id])

        # Cherries and Bananas go; the voter keeps only one pick among what remains.
        response = await client.patch(
            f"/posts/{first_post.id}",
            json=edit_payload(
                poll=poll_payload(
                    options_per_user=1,
                    options=[{"id": options[0].id, "text": "Apples"}, {"text": "New"}],
                )
            ),
        )

        assert response.status_code == 200


class TestGetThreadPoll:
    async def test_thread_without_poll_has_none(self, client, create, db_session):
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )

        response = await client.get(f"/threads/{thread.id}")

        assert response.json()["poll"] is None

    async def test_results_are_hidden_from_a_viewer_who_has_not_voted(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        options = await make_poll(db_session, thread)
        await cast_votes(db_session, thread, await create(UserFactory), [options[0].id])

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["show_results"] is False
        assert poll["total_voters"] is None
        assert [o["votes"] for o in poll["options"]] == [None, None, None]
        assert [o["text"] for o in poll["options"]] == [
            "Apples",
            "Bananas",
            "Cherries",
        ]

    async def test_moderators_get_no_extra_visibility(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        await grant(db_session, user, thread.forum, Verbs.FORUM_MODERATE)
        await make_poll(db_session, thread)

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["show_results"] is False

    async def test_thread_creator_sees_results(self, authed_client, create, db_session):
        client, user = authed_client
        thread, _first = await make_thread(create, db_session, user)
        options = await make_poll(db_session, thread)
        await cast_votes(db_session, thread, await create(UserFactory), [options[1].id])

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["show_results"] is True
        assert poll["total_voters"] == 1
        assert [o["votes"] for o in poll["options"]] == [0, 1, 0]
        assert poll["voted"] is False

    async def test_voter_sees_results_and_their_votes(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        options = await make_poll(db_session, thread)
        await cast_votes(db_session, thread, user, [options[2].id])
        await cast_votes(db_session, thread, await create(UserFactory), [options[2].id])

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["voted"] is True
        assert poll["my_votes"] == [options[2].id]
        assert poll["total_voters"] == 2
        assert [o["votes"] for o in poll["options"]] == [0, 0, 2]

    async def test_locked_thread_shows_results_to_guests(
        self, client, create, db_session
    ):
        thread, _first = await make_thread(
            create,
            db_session,
            await create(UserFactory),
            options=Thread.Options(locked=True),
        )
        options = await make_poll(db_session, thread)
        await cast_votes(db_session, thread, await create(UserFactory), [options[0].id])

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["show_results"] is True
        assert [o["votes"] for o in poll["options"]] == [1, 0, 0]
        assert poll["can_vote"] is False

    async def test_member_cannot_vote_in_a_locked_thread(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        thread, _first = await make_thread(
            create,
            db_session,
            await create(UserFactory),
            options=Thread.Options(locked=True),
        )
        await make_poll(db_session, thread)

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["can_vote"] is False

    async def test_guest_cannot_vote(self, client, create, db_session):
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        await make_poll(db_session, thread)

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["can_vote"] is False
        assert poll["my_votes"] == []

    async def test_member_can_vote(self, authed_client, create, db_session):
        client, _user = authed_client
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        await make_poll(db_session, thread)

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["can_vote"] is True

    async def test_cannot_vote_without_write_permission(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[])
        await grant(db_session, user, forum, Verbs.FORUM_READ)
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory), forum=forum
        )
        await make_poll(db_session, thread)

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["can_vote"] is False

    @pytest.mark.parametrize(
        ("allow_revoting", "can_vote"), [(False, False), (True, True)]
    )
    async def test_voted_viewer_can_vote_only_if_revoting_is_allowed(
        self, authed_client, create, db_session, allow_revoting, can_vote
    ):
        client, user = authed_client
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        options = await make_poll(db_session, thread, allow_revoting=allow_revoting)
        await cast_votes(db_session, thread, user, [options[0].id])

        poll = (await client.get(f"/threads/{thread.id}")).json()["poll"]

        assert poll["can_vote"] is can_vote


class TestGetPostPoll:
    async def test_first_post_author_gets_poll_with_counts(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, first_post = await make_thread(create, db_session, user)
        options = await make_poll(db_session, thread)
        await cast_votes(db_session, thread, await create(UserFactory), [options[0].id])

        poll = (await client.get(f"/posts/{first_post.id}")).json()["poll"]

        assert poll["show_results"] is True
        assert [o["votes"] for o in poll["options"]] == [1, 0, 0]

    async def test_moderator_gets_poll_with_counts(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, first_post = await make_thread(
            create, db_session, await create(UserFactory)
        )
        await grant(db_session, user, thread.forum, Verbs.FORUM_MODERATE)
        await make_poll(db_session, thread)

        poll = (await client.get(f"/posts/{first_post.id}")).json()["poll"]

        assert poll["show_results"] is True

    async def test_viewer_who_cannot_edit_gets_no_poll(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        thread, first_post = await make_thread(
            create, db_session, await create(UserFactory)
        )
        await make_poll(db_session, thread)

        response = await client.get(f"/posts/{first_post.id}")

        assert response.json()["poll"] is None

    async def test_reply_gets_no_poll(self, authed_client, create, db_session):
        client, user = authed_client
        thread, _first = await make_thread(create, db_session, user)
        await make_poll(db_session, thread)
        reply = await create(PostFactory, thread=thread, author=user)

        response = await client.get(f"/posts/{reply.id}")

        assert response.json()["poll"] is None


class TestVote:
    async def setup_poll(self, authed_client, create, db_session, **poll_overrides):
        client, user = authed_client
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        options = await make_poll(db_session, thread, **poll_overrides)
        return client, user, thread, options

    async def vote(self, client, thread, option_ids):
        return await client.put(
            f"/threads/{thread.id}/poll/vote", json={"option_ids": option_ids}
        )

    async def test_vote_requires_auth(self, client, create, db_session):
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )
        options = await make_poll(db_session, thread)

        response = await self.vote(client, thread, [options[0].id])

        assert response.status_code == 403

    async def test_vote_is_recorded_and_results_returned(
        self, authed_client, create, db_session
    ):
        client, user, thread, options = await self.setup_poll(
            authed_client, create, db_session
        )

        response = await self.vote(client, thread, [options[1].id])

        assert response.status_code == 200
        body = response.json()
        assert body["voted"] is True
        assert body["my_votes"] == [options[1].id]
        assert body["show_results"] is True
        assert [o["votes"] for o in body["options"]] == [0, 1, 0]
        assert await PollRepository(db_session, principal=user).user_votes(
            thread.id, user.id
        ) == [options[1].id]

    async def test_multiple_choice_vote(self, authed_client, create, db_session):
        client, _user, thread, options = await self.setup_poll(
            authed_client, create, db_session, options_per_user=2
        )

        response = await self.vote(client, thread, [options[0].id, options[2].id])

        assert response.status_code == 200
        assert sorted(response.json()["my_votes"]) == [options[0].id, options[2].id]

    async def test_unknown_thread_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.put(
            "/threads/999999/poll/vote", json={"option_ids": [1]}
        )

        assert response.status_code == 404

    async def test_thread_without_poll_returns_404(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory)
        )

        response = await self.vote(client, thread, [1])

        assert response.status_code == 404
        assert response.json()["errors"][0]["detail"] == "Poll not found"

    async def test_unreadable_thread_returns_404(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[])
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory), forum=forum
        )
        options = await make_poll(db_session, thread)

        response = await self.vote(client, thread, [options[0].id])

        assert response.status_code == 404

    async def test_locked_thread_returns_403_even_for_moderators(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, _first = await make_thread(
            create,
            db_session,
            await create(UserFactory),
            options=Thread.Options(locked=True),
        )
        await grant(db_session, user, thread.forum, Verbs.FORUM_MODERATE)
        options = await make_poll(db_session, thread)

        response = await self.vote(client, thread, [options[0].id])

        assert response.status_code == 403

    async def test_without_write_permission_returns_403(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[])
        await grant(db_session, user, forum, Verbs.FORUM_READ)
        thread, _first = await make_thread(
            create, db_session, await create(UserFactory), forum=forum
        )
        options = await make_poll(db_session, thread)

        response = await self.vote(client, thread, [options[0].id])

        assert response.status_code == 403

    async def test_voting_again_without_revoting_returns_403(
        self, authed_client, create, db_session
    ):
        client, user, thread, options = await self.setup_poll(
            authed_client, create, db_session
        )
        await cast_votes(db_session, thread, user, [options[0].id])

        response = await self.vote(client, thread, [options[1].id])

        assert response.status_code == 403
        assert await PollRepository(db_session, principal=user).user_votes(
            thread.id, user.id
        ) == [options[0].id]

    async def test_revoting_replaces_the_previous_votes(
        self, authed_client, create, db_session
    ):
        client, user, thread, options = await self.setup_poll(
            authed_client, create, db_session, allow_revoting=True
        )
        await cast_votes(db_session, thread, user, [options[0].id])

        response = await self.vote(client, thread, [options[1].id])

        assert response.status_code == 200
        assert response.json()["my_votes"] == [options[1].id]
        assert await count(db_session, PollVote) == 1

    async def test_empty_vote_returns_400(self, authed_client, create, db_session):
        client, _user, thread, _options = await self.setup_poll(
            authed_client, create, db_session
        )

        response = await self.vote(client, thread, [])

        assert response.status_code == 400

    async def test_too_many_options_returns_400(
        self, authed_client, create, db_session
    ):
        client, _user, thread, options = await self.setup_poll(
            authed_client, create, db_session
        )

        response = await self.vote(client, thread, [options[0].id, options[1].id])

        assert response.status_code == 400

    async def test_duplicate_options_return_400(
        self, authed_client, create, db_session
    ):
        client, _user, thread, options = await self.setup_poll(
            authed_client, create, db_session, options_per_user=2
        )

        response = await self.vote(client, thread, [options[0].id, options[0].id])

        assert response.status_code == 400

    async def test_option_from_another_poll_returns_400(
        self, authed_client, create, db_session
    ):
        client, _user, thread, _options = await self.setup_poll(
            authed_client, create, db_session
        )
        other_thread, _ = await make_thread(
            create, db_session, await create(UserFactory)
        )
        [foreign, *_rest] = await make_poll(db_session, other_thread)

        response = await self.vote(client, thread, [foreign.id])

        assert response.status_code == 400
        assert await count(db_session, PollVote) == 0
