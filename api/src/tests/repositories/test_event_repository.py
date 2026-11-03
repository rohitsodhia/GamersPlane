from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Event, EventRecipient, Post
from app.repositories import EventRepository
from tests.factories import ActivatedUserFactory, PostFactory, ThreadFactory
from tests.game_forum import make_character, make_game_forum


@pytest.fixture(autouse=True)
async def _isolate(wrap_in_savepoint):
    """Roll each test back (the tests here don't use the client fixture)."""


@pytest.fixture
async def event(create, db_session):
    post = await create(PostFactory)
    event = Event(
        type=Event.Types.MENTION,
        actor_id=post.author_id,
        post_id=post.id,
        thread_id=post.thread_id,
    )
    db_session.add(event)
    await db_session.flush()
    return event


class TestUpsertEvent:
    async def test_a_repeat_reuses_the_event_and_resets_current_recipients(
        self, create, db_session
    ):
        gf = await make_game_forum(create, db_session)
        applicant = await create(ActivatedUserFactory)
        new_actor = await create(ActivatedUserFactory)
        stayer = await create(ActivatedUserFactory)
        newcomer = await create(ActivatedUserFactory)
        former = await create(ActivatedUserFactory)
        repo = EventRepository(db_session)
        first = await repo.upsert_event(
            Event.Types.GAME_APPLICATION,
            applicant.id,
            {stayer.id, former.id},
            game_id=gf.game.id,
            subject_user_id=applicant.id,
        )
        old_created_at = first.created_at
        read_at = datetime(2026, 1, 1, tzinfo=UTC)
        for user in (stayer, former):
            row = await db_session.get(EventRecipient, (first.id, user.id))
            row.read_at = row.dismissed_at = read_at
        await db_session.flush()

        again = await repo.upsert_event(
            Event.Types.GAME_APPLICATION,
            new_actor.id,
            {stayer.id, newcomer.id},
            game_id=gf.game.id,
            subject_user_id=applicant.id,
        )

        assert again.id == first.id
        assert again.actor_id == new_actor.id
        assert again.created_at > old_created_at
        rows = {
            row.user_id: row for row in await db_session.scalars(select(EventRecipient))
        }
        assert set(rows) == {stayer.id, newcomer.id, former.id}
        for user in (stayer, newcomer):
            assert (rows[user.id].read_at, rows[user.id].dismissed_at) == (None, None)
        # Someone no longer a recipient keeps their row as it was.
        assert rows[former.id].dismissed_at == read_at

    async def test_a_character_is_keyed_by_the_character_alone(
        self, create, db_session
    ):
        gf = await make_game_forum(create, db_session)
        owner = await create(ActivatedUserFactory)
        character = await make_character(db_session, owner, gf.game, approved=False)
        other_character = await make_character(
            db_session, owner, gf.game, approved=False
        )
        repo = EventRepository(db_session)

        events = [
            await repo.upsert_event(
                Event.Types.CHARACTER_SUBMITTED,
                owner.id,
                {gf.gm.id},
                game_id=gf.game.id,
                character_id=target.id,
            )
            for target in (character, other_character, character)
        ]

        assert events[0].id == events[2].id
        assert events[0].id != events[1].id

    async def test_no_recipients_writes_nothing(self, create, db_session):
        gf = await make_game_forum(create, db_session)
        user = await create(ActivatedUserFactory)

        result = await EventRepository(db_session).upsert_event(
            Event.Types.GAME_INVITE,
            gf.gm.id,
            set(),
            game_id=gf.game.id,
            subject_user_id=user.id,
        )

        assert result is None
        assert await db_session.scalar(select(Event)) is None


class TestEventConstraints:
    async def test_an_event_missing_its_types_columns_is_rejected(
        self, create, db_session
    ):
        user = await create(ActivatedUserFactory)

        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                # An invite needs its game and subject.
                db_session.add(Event(type=Event.Types.GAME_INVITE, actor_id=user.id))
                await db_session.flush()


class TestAddRecipients:
    async def test_a_user_who_already_has_a_row_keeps_their_read_time(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        newcomer = await create(ActivatedUserFactory)
        read_at = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add(
            EventRecipient(event_id=event.id, user_id=user.id, read_at=read_at)
        )
        await db_session.flush()

        await EventRepository(db_session).add_recipients(
            event.id, {user.id, newcomer.id}
        )

        rows = (
            await db_session.execute(
                select(EventRecipient.user_id, EventRecipient.read_at)
            )
        ).all()
        assert dict(rows) == {user.id: read_at, newcomer.id: None}


class TestMarkRead:
    async def test_marking_again_keeps_the_first_read_time(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        first = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add(EventRecipient(event_id=event.id, user_id=user.id))
        await db_session.flush()
        repo = EventRepository(db_session)
        assert await repo.mark_read(user.id, event.id) is True
        row = await db_session.get(EventRecipient, (event.id, user.id))
        row.read_at = first
        await db_session.flush()

        assert await repo.mark_read(user.id, event.id) is True

        assert row.read_at == first

    async def test_a_user_without_a_row_is_reported_and_nothing_changes(
        self, create, db_session, event
    ):
        owner = await create(ActivatedUserFactory)
        stranger = await create(ActivatedUserFactory)
        db_session.add(EventRecipient(event_id=event.id, user_id=owner.id))
        await db_session.flush()

        assert (
            await EventRepository(db_session).mark_read(stranger.id, event.id) is False
        )

        row = await db_session.get(EventRecipient, (event.id, owner.id))
        assert row.read_at is None


class TestDismiss:
    async def test_dismissing_sets_both_times_and_keeps_an_earlier_read_time(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        unread = await create(ActivatedUserFactory)
        read_at = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add_all(
            [
                EventRecipient(event_id=event.id, user_id=user.id, read_at=read_at),
                EventRecipient(event_id=event.id, user_id=unread.id),
            ]
        )
        await db_session.flush()
        repo = EventRepository(db_session)

        assert await repo.dismiss(user.id, event.id) is True
        assert await repo.dismiss(unread.id, event.id) is True

        kept = await db_session.get(EventRecipient, (event.id, user.id))
        fresh = await db_session.get(EventRecipient, (event.id, unread.id))
        assert kept.read_at == read_at
        assert kept.dismissed_at is not None
        assert fresh.read_at is not None
        assert fresh.dismissed_at == fresh.read_at

    async def test_dismissing_again_keeps_the_first_dismissal(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        first = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add(
            EventRecipient(
                event_id=event.id, user_id=user.id, read_at=first, dismissed_at=first
            )
        )
        await db_session.flush()

        assert await EventRepository(db_session).dismiss(user.id, event.id) is True

        row = await db_session.get(EventRecipient, (event.id, user.id))
        assert row.dismissed_at == first

    async def test_a_user_without_a_row_is_reported(self, create, event, db_session):
        stranger = await create(ActivatedUserFactory)

        assert await EventRepository(db_session).dismiss(stranger.id, event.id) is False


class TestDismissForPosts:
    async def test_only_the_users_rows_for_published_posts_of_the_thread(
        self, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        other = await create(ActivatedUserFactory)
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)
        draft = await create(PostFactory, thread=thread, state=Post.States.DRAFT)
        elsewhere = await create(PostFactory)
        unlisted = await create(PostFactory, thread=thread)
        events = {}
        for name, target in {
            "post": post,
            "draft": draft,
            "elsewhere": elsewhere,
            "unlisted": unlisted,
        }.items():
            events[name] = Event(
                type=Event.Types.MENTION,
                actor_id=target.author_id,
                post_id=target.id,
                thread_id=target.thread_id,
            )
            db_session.add(events[name])
        await db_session.flush()
        db_session.add_all(
            [EventRecipient(event_id=e.id, user_id=user.id) for e in events.values()]
            + [EventRecipient(event_id=events["post"].id, user_id=other.id)]
        )
        await db_session.flush()

        changed = await EventRepository(db_session).dismiss_for_posts(
            user.id, thread.id, [post.id, draft.id, elsewhere.id]
        )

        assert changed == 1
        rows = {
            (row.event_id, row.user_id): row
            for row in await db_session.scalars(select(EventRecipient))
        }
        dismissed = rows[(events["post"].id, user.id)]
        assert dismissed.dismissed_at is not None
        assert dismissed.read_at is not None
        own = {e.id for e in events.values()}
        assert [
            key
            for key, row in rows.items()
            if key[0] in own
            and row.dismissed_at is not None
            and key != (events["post"].id, user.id)
        ] == []

    async def test_an_earlier_read_is_kept_and_a_dismissed_row_is_left_alone(
        self, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        thread = await create(ThreadFactory)
        read_post = await create(PostFactory, thread=thread)
        dismissed_post = await create(PostFactory, thread=thread)
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        later = datetime(2026, 2, 1, tzinfo=UTC)
        rows = {}
        for name, post, columns in (
            ("read", read_post, {"read_at": earlier}),
            (
                "dismissed",
                dismissed_post,
                {"read_at": earlier, "dismissed_at": later},
            ),
        ):
            mention = Event(
                type=Event.Types.MENTION,
                actor_id=post.author_id,
                post_id=post.id,
                thread_id=thread.id,
            )
            db_session.add(mention)
            await db_session.flush()
            rows[name] = EventRecipient(event_id=mention.id, user_id=user.id, **columns)
            db_session.add(rows[name])
        await db_session.flush()

        changed = await EventRepository(db_session).dismiss_for_posts(
            user.id, thread.id, [read_post.id, dismissed_post.id]
        )

        assert changed == 1
        await db_session.refresh(rows["read"])
        await db_session.refresh(rows["dismissed"])
        assert rows["read"].read_at == earlier
        assert rows["read"].dismissed_at is not None
        assert rows["dismissed"].dismissed_at == later

    async def test_an_empty_list_changes_nothing(self, create, db_session, event):
        user = await create(ActivatedUserFactory)
        db_session.add(EventRecipient(event_id=event.id, user_id=user.id))
        await db_session.flush()

        changed = await EventRepository(db_session).dismiss_for_posts(
            user.id, event.thread_id, []
        )

        assert changed == 0


class TestMarkAllRead:
    async def test_only_the_users_unread_rows_are_touched(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        other = await create(ActivatedUserFactory)
        post = await create(PostFactory)
        second = Event(
            type=Event.Types.MENTION,
            actor_id=post.author_id,
            post_id=post.id,
            thread_id=post.thread_id,
        )
        db_session.add(second)
        await db_session.flush()
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add_all(
            [
                EventRecipient(event_id=event.id, user_id=user.id),
                EventRecipient(event_id=second.id, user_id=user.id, read_at=earlier),
                EventRecipient(event_id=event.id, user_id=other.id),
            ]
        )
        await db_session.flush()

        updated = await EventRepository(db_session).mark_all_read(user.id)

        assert updated == 1
        rows = {
            (row.event_id, row.user_id): row.read_at
            for row in await db_session.scalars(select(EventRecipient))
        }
        assert rows[(event.id, user.id)] is not None
        assert rows[(second.id, user.id)] == earlier
        assert rows[(event.id, other.id)] is None
