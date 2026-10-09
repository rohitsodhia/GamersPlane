from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import ForumRead, Post, ThreadRead
from app.repositories.read_tracking_repository import ReadTrackingRepository
from app.repositories.thread_repository import ThreadRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory, UserFactory

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def day(n: int) -> datetime:
    return BASE + timedelta(days=n)


class TestReadTrackingRepository:
    @pytest.fixture
    async def user(self, create):
        return await create(UserFactory)

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint, user):
        return ReadTrackingRepository(db_session, principal=user)

    @pytest.fixture
    async def root(self, create, wrap_in_savepoint):
        return await create(ForumFactory, id=0, heritage=[])

    @pytest.fixture
    async def parent(self, create, root):
        return await create(ForumFactory, heritage=[root.id], parent_id=root.id)

    @pytest.fixture
    async def child(self, create, parent):
        return await create(ForumFactory, heritage=[0, parent.id], parent_id=parent.id)

    @pytest.fixture
    def add_post(self, create, db_session):
        thread_repository = ThreadRepository(db_session, principal=None)

        async def _add_post(thread, published_at, **kwargs):
            post = await create(
                PostFactory, thread=thread, published_at=published_at, **kwargs
            )
            await thread_repository.attach_new_post(thread, post)
            return post

        return _add_post

    @pytest.fixture
    def make_thread(self, create, add_post):
        async def _make_thread(forum, *post_days):
            thread = await create(ThreadFactory, forum=forum)
            for post_day in post_days:
                await add_post(thread, day(post_day))
            return thread

        return _make_thread

    @pytest.fixture
    def thread_read_row(self, db_session, user):
        async def _row(thread):
            return (
                await db_session.execute(
                    select(ThreadRead.read_until, ThreadRead.pinned).where(
                        ThreadRead.user_id == user.id, ThreadRead.thread_id == thread.id
                    )
                )
            ).first()

        return _row

    @pytest.fixture
    def set_forum_cutoff(self, db_session, user):
        async def _set(forum, read_until):
            db_session.add(
                ForumRead(user_id=user.id, forum_id=forum.id, read_until=read_until)
            )
            await db_session.flush()

        return _set

    # Thread unread status

    async def test_unvisited_thread_without_forum_cutoff_is_unread(
        self, repository, make_thread, parent
    ):
        thread = await make_thread(parent, 1)

        assert await repository.is_thread_unread(thread)
        assert await repository.unread_thread_ids([thread]) == {thread.id}

    async def test_thread_without_posts_is_never_unread(
        self, repository, make_thread, parent
    ):
        thread = await make_thread(parent)

        assert not await repository.is_thread_unread(thread)
        assert await repository.unread_thread_ids([thread]) == set()

    async def test_forum_cutoff_after_last_post_makes_thread_read(
        self, repository, make_thread, parent, set_forum_cutoff
    ):
        thread = await make_thread(parent, 1)
        await set_forum_cutoff(parent, day(1))

        assert not await repository.is_thread_unread(thread)
        assert await repository.unread_thread_ids([thread]) == set()

    async def test_post_after_forum_cutoff_is_unread(
        self, repository, make_thread, parent, set_forum_cutoff
    ):
        thread = await make_thread(parent, 1, 3)
        await set_forum_cutoff(parent, day(2))

        assert await repository.is_thread_unread(thread)

    async def test_ancestor_forum_cutoff_hides_descendant_thread(
        self, repository, make_thread, child, parent, set_forum_cutoff
    ):
        thread = await make_thread(child, 1)
        await set_forum_cutoff(parent, day(5))

        assert not await repository.is_thread_unread(thread)
        assert await repository.unread_thread_ids([thread]) == set()

    async def test_descendant_forum_cutoff_does_not_affect_ancestor_thread(
        self, repository, make_thread, child, parent, set_forum_cutoff
    ):
        thread = await make_thread(parent, 1)
        await set_forum_cutoff(child, day(5))

        assert await repository.is_thread_unread(thread)

    async def test_thread_read_uses_later_of_own_and_forum_marker(
        self, repository, make_thread, parent, set_forum_cutoff
    ):
        thread = await make_thread(parent, 1, 4)
        await set_forum_cutoff(parent, day(2))
        await repository.mark_viewed(thread, day(4))

        assert await repository.thread_read_point(thread) == day(4)
        assert not await repository.is_thread_unread(thread)

    async def test_unread_thread_ids_picks_only_unread_threads(
        self, repository, make_thread, parent
    ):
        read = await make_thread(parent, 1)
        unread = await make_thread(parent, 2)
        await repository.mark_thread_read(read)

        assert await repository.unread_thread_ids([read, unread]) == {unread.id}

    async def test_other_users_marks_do_not_apply(
        self, create, db_session, repository, make_thread, parent
    ):
        thread = await make_thread(parent, 1)
        other = ReadTrackingRepository(db_session, principal=await create(UserFactory))
        await other.mark_thread_read(thread)

        assert await repository.is_thread_unread(thread)

    # mark_viewed

    async def test_mark_viewed_creates_unpinned_row(
        self, repository, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1, 2)

        await repository.mark_viewed(thread, day(1))

        assert tuple(await thread_read_row(thread)) == (day(1), False)
        assert await repository.is_thread_unread(thread)

    async def test_mark_viewed_never_moves_read_until_backwards(
        self, repository, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1, 2, 3)
        await repository.mark_viewed(thread, day(3))

        await repository.mark_viewed(thread, day(1))

        assert (await thread_read_row(thread)).read_until == day(3)

    async def test_mark_viewed_advances_read_until(
        self, repository, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1, 2, 3)
        await repository.mark_viewed(thread, day(1))

        await repository.mark_viewed(thread, day(2))

        assert (await thread_read_row(thread)).read_until == day(2)

    async def test_mark_viewed_fills_null_read_until_and_keeps_pin(
        self, repository, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1)
        await repository.mark_thread_unread(thread)

        await repository.mark_viewed(thread, day(1))

        assert tuple(await thread_read_row(thread)) == (day(1), True)

    # mark_thread_read / mark_thread_unread

    async def test_mark_thread_read_sets_last_post_and_clears_pin(
        self, repository, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1, 2)
        await repository.mark_thread_unread(thread)

        await repository.mark_thread_read(thread)

        assert tuple(await thread_read_row(thread)) == (day(2), False)
        assert not await repository.is_thread_unread(thread)

    async def test_new_post_after_mark_thread_read_makes_thread_unread(
        self, repository, make_thread, add_post, parent
    ):
        thread = await make_thread(parent, 1)
        await repository.mark_thread_read(thread)

        await add_post(thread, day(2))

        assert await repository.is_thread_unread(thread)

    async def test_mark_thread_unread_reads_up_to_second_newest_post(
        self, repository, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1, 2, 3)
        await repository.mark_thread_read(thread)

        await repository.mark_thread_unread(thread)

        assert tuple(await thread_read_row(thread)) == (day(2), True)
        assert await repository.is_thread_unread(thread)

    async def test_mark_thread_unread_ignores_drafts_and_deleted_posts(
        self, repository, create, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1, 3)
        await create(
            PostFactory,
            thread=thread,
            state=Post.States.DRAFT,
            published_at=day(5),
        )
        await create(PostFactory, thread=thread, published_at=day(4), deleted=day(6))

        await repository.mark_thread_unread(thread)

        assert (await thread_read_row(thread)).read_until == day(1)

    async def test_mark_thread_unread_on_single_post_thread(
        self, repository, make_thread, parent, thread_read_row
    ):
        thread = await make_thread(parent, 1)
        await repository.mark_thread_read(thread)

        await repository.mark_thread_unread(thread)

        assert tuple(await thread_read_row(thread)) == (None, True)
        assert await repository.is_thread_unread(thread)

    async def test_pinned_thread_ignores_higher_forum_cutoff(
        self, repository, make_thread, parent, set_forum_cutoff
    ):
        thread = await make_thread(parent, 1, 2)
        await repository.mark_thread_unread(thread)
        await set_forum_cutoff(parent, day(10))

        assert await repository.thread_read_point(thread) == day(1)
        assert await repository.is_thread_unread(thread)
        assert await repository.unread_thread_ids([thread]) == {thread.id}
        assert await repository.unread_forum_ids([parent.id]) == {parent.id}

    # mark_forum_read

    async def test_mark_forum_read_covers_subtree_latest_post(
        self, repository, make_thread, parent, child, db_session, user
    ):
        top = await make_thread(parent, 1)
        nested = await make_thread(child, 3)

        await repository.mark_forum_read(parent)

        stored = await db_session.scalar(
            select(ForumRead.read_until).where(
                ForumRead.user_id == user.id, ForumRead.forum_id == parent.id
            )
        )
        assert stored == day(3)
        assert await repository.unread_thread_ids([top, nested]) == set()

    async def test_mark_forum_read_clears_pins_in_subtree_only(
        self, repository, make_thread, root, parent, child, create, thread_read_row
    ):
        sibling = await create(ForumFactory, heritage=[root.id], parent_id=root.id)
        in_parent = await make_thread(parent, 1, 2)
        in_child = await make_thread(child, 1, 2)
        outside = await make_thread(sibling, 1, 2)
        for thread in (in_parent, in_child, outside):
            await repository.mark_thread_unread(thread)

        await repository.mark_forum_read(parent)

        assert await thread_read_row(in_parent) is None
        assert await thread_read_row(in_child) is None
        assert (await thread_read_row(outside)).pinned is True
        assert await repository.unread_thread_ids([in_parent, in_child, outside]) == {
            outside.id
        }

    async def test_mark_forum_read_does_not_cover_sibling_forum(
        self, repository, make_thread, root, parent, create
    ):
        sibling = await create(ForumFactory, heritage=[root.id], parent_id=root.id)
        thread = await make_thread(sibling, 1)

        await repository.mark_forum_read(parent)

        assert await repository.is_thread_unread(thread)

    async def test_mark_forum_read_without_posts_does_nothing(
        self, repository, parent, db_session
    ):
        await repository.mark_forum_read(parent)

        assert await db_session.scalar(select(ForumRead.forum_id)) is None

    async def test_mark_site_root_read_marks_everything_read(
        self, repository, make_thread, root, parent, child
    ):
        top = await make_thread(parent, 1)
        nested = await make_thread(child, 2)

        await repository.mark_forum_read(root)

        assert await repository.unread_thread_ids([top, nested]) == set()
        assert await repository.unread_forum_ids([parent.id, child.id]) == set()

    async def test_new_post_after_mark_forum_read_makes_forum_unread_again(
        self, repository, make_thread, add_post, parent, child
    ):
        thread = await make_thread(child, 1)
        await repository.mark_forum_read(parent)

        await add_post(thread, day(2))

        assert await repository.unread_forum_ids([parent.id, child.id]) == {
            parent.id,
            child.id,
        }

    async def test_initialize_for_user_marks_existing_threads_read(
        self, repository, make_thread, add_post, parent
    ):
        old = await make_thread(parent, -400)
        await repository.initialize_for_user()
        new = await make_thread(parent)
        await add_post(new, datetime.now(UTC) + timedelta(days=1))

        assert await repository.unread_thread_ids([old, new]) == {new.id}

    async def test_initialize_for_user_does_not_overwrite_existing_marker(
        self, repository, db_session, user, root, set_forum_cutoff
    ):
        await set_forum_cutoff(root, day(1))

        await repository.initialize_for_user()

        stored = await db_session.scalar(
            select(ForumRead.read_until).where(
                ForumRead.user_id == user.id, ForumRead.forum_id == 0
            )
        )
        assert stored == day(1)

    async def test_mark_forum_read_ignores_deleted_threads_for_cutoff(
        self, repository, make_thread, parent, db_session, user
    ):
        await make_thread(parent, 1)
        deleted = await make_thread(parent, 9)
        deleted.deleted = day(10)
        await db_session.flush()

        await repository.mark_forum_read(parent)

        stored = await db_session.scalar(
            select(ForumRead.read_until).where(ForumRead.user_id == user.id)
        )
        assert stored == day(1)

    # unread_forum_ids

    async def test_unread_forum_ids_rolls_up_to_ancestors(
        self, repository, make_thread, root, parent, child
    ):
        await make_thread(child, 1)

        unread = await repository.unread_forum_ids([root.id, parent.id, child.id])

        assert unread == {root.id, parent.id, child.id}

    async def test_unread_forum_ids_excludes_forums_without_unread_threads(
        self, repository, make_thread, parent, child
    ):
        read = await make_thread(child, 1)
        await repository.mark_thread_read(read)
        await make_thread(parent, 2)

        unread = await repository.unread_forum_ids([parent.id, child.id])

        assert unread == {parent.id}

    async def test_unreadable_child_forum_does_not_make_parent_unread(
        self, repository, make_thread, parent, child
    ):
        await make_thread(child, 1)

        unread = await repository.unread_forum_ids([parent.id])

        assert unread == set()

    async def test_unread_forum_ids_only_returns_requested_forums(
        self, repository, make_thread, root, parent, child
    ):
        await make_thread(child, 1)

        unread = await repository.unread_forum_ids([child.id])

        assert unread == {child.id}

    async def test_unread_forum_ids_applies_ancestor_cutoff(
        self, repository, make_thread, parent, child, set_forum_cutoff
    ):
        await make_thread(child, 1)
        await set_forum_cutoff(parent, day(2))

        assert await repository.unread_forum_ids([parent.id, child.id]) == set()

    async def test_unread_forum_ids_ignores_deleted_threads(
        self, repository, make_thread, parent, db_session
    ):
        thread = await make_thread(parent, 1)
        thread.deleted = day(2)
        await db_session.flush()

        assert await repository.unread_forum_ids([parent.id]) == set()

    async def test_unread_forum_ids_counts_pin_with_no_read_point(
        self, repository, make_thread, parent
    ):
        thread = await make_thread(parent, 1)
        await repository.mark_thread_unread(thread)

        assert await repository.unread_forum_ids([parent.id]) == {parent.id}

    async def test_unread_forum_ids_pinned_thread_in_unreadable_forum_ignored(
        self, repository, make_thread, parent, child
    ):
        thread = await make_thread(child, 1, 2)
        await repository.mark_thread_unread(thread)

        assert await repository.unread_forum_ids([parent.id]) == set()

    async def test_unread_forum_ids_forum_cutoff_beats_older_own_marker(
        self, repository, make_thread, parent, set_forum_cutoff
    ):
        thread = await make_thread(parent, 1, 3)
        await repository.mark_viewed(thread, day(1))
        await set_forum_cutoff(parent, day(3))

        assert await repository.unread_forum_ids([parent.id]) == set()
        assert await repository.thread_read_point(thread) == day(3)

    async def test_unread_forum_ids_ignores_threads_without_posts(
        self, repository, make_thread, parent
    ):
        await make_thread(parent)

        assert await repository.unread_forum_ids([parent.id]) == set()

    async def test_unread_forum_ids_with_no_matching_forums(self, repository):
        assert await repository.unread_forum_ids([]) == set()
        assert await repository.unread_forum_ids([9999]) == set()

    async def test_forum_cutoff_is_latest_marker_up_the_tree(
        self, repository, root, parent, child, set_forum_cutoff
    ):
        assert await repository.forum_cutoff(child) is None

        await set_forum_cutoff(root, day(5))
        await set_forum_cutoff(parent, day(2))

        assert await repository.forum_cutoff(child) == day(5)
