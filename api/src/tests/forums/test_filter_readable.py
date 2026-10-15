from datetime import UTC, datetime

import pytest

from app.forums.functions import filter_readable_forum_ids
from app.models import RolePermission
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import ForumFactory, UserFactory
from tests.game_forum import grant

Verbs = RolePermission.ValidPermissions


@pytest.fixture(autouse=True)
async def _open_site_root(wrap_in_savepoint, open_forums):
    await open_forums(SITE_ROOT_FORUM_ID)


class TestFilterReadableForumIds:
    @pytest.fixture
    async def forums(self, create):
        return (
            await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID]),
            await create(ForumFactory, heritage=[]),
        )

    async def test_keeps_only_the_forums_the_principal_can_read(
        self, db_session, create, forums
    ):
        open_forum, closed_forum = forums
        user = await create(UserFactory)
        await grant(db_session, user, closed_forum, Verbs.FORUM_READ)

        member = await filter_readable_forum_ids(
            db_session, user, [open_forum.id, closed_forum.id]
        )
        guest = await filter_readable_forum_ids(
            db_session, None, [open_forum.id, closed_forum.id]
        )

        assert member == {open_forum.id, closed_forum.id}
        assert guest == {open_forum.id}

    async def test_nothing_asked_or_unknown_or_deleted_forums_are_not_readable(
        self, db_session, create, forums
    ):
        deleted = await create(
            ForumFactory, heritage=[SITE_ROOT_FORUM_ID], deleted=datetime.now(UTC)
        )

        assert await filter_readable_forum_ids(db_session, None, []) == set()
        assert await filter_readable_forum_ids(db_session, None, [999999]) == set()
        assert await filter_readable_forum_ids(db_session, None, [deleted.id]) == set()
