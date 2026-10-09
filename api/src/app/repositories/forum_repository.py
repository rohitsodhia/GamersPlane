from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy import ScalarResult, Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException, ValidationError
from app.models import Forum, User

# The forum index; every other forum descends from it.
SITE_ROOT_FORUM_ID = 0
# The index, General, Game Forums and Announcements: the site's structure hangs
# off these, so they can't be deleted or renamed.
PROTECTED_FORUM_IDS = frozenset({SITE_ROOT_FORUM_ID, 1, 2, 3})


class ForumRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def add(
        self,
        title: str,
        forum_type: Forum.ForumTypes,
        parent_id: int,
        description: str | None = None,
        game_id: int | None = None,
    ) -> Forum:
        parent_heritage = await self.db_session.scalar(
            select(Forum.heritage).where(Forum.id == parent_id)
        )
        if parent_heritage is None:
            raise NotFoundException(f'Parent forum "{parent_id}" does not exist')

        # Deleted children keep their slots, so count past the highest order
        # rather than the number of children.
        last_order = await self.db_session.scalar(
            select(func.max(Forum.order))
            .where(Forum.parent_id == parent_id)
            .execution_options(skip_filter=True)
        )
        obj = Forum(
            title=title,
            description=description,
            forum_type=forum_type,
            parent_id=parent_id,
            heritage=parent_heritage + [parent_id],
            order=(last_order or 0) + 1,
            game_id=game_id,
        )
        self.db_session.add(obj)
        await self.db_session.flush()
        return obj

    async def get(self, forum_id: int) -> Forum | None:
        forum = await self.db_session.get(Forum, forum_id)
        return forum

    async def get_multiple(self, forum_ids: list[int]) -> ScalarResult[Forum]:
        return await self.db_session.scalars(
            select(Forum).where(Forum.id.in_(forum_ids))
        )

    async def get_descendants(
        self, forum_id: int, only_game_ids: Collection[int] | None = None
    ) -> ScalarResult[Forum]:
        """Every forum below ``forum_id``.

        ``only_game_ids`` limits game forums to those games; non-game forums are
        unaffected.
        """
        query = (
            select(Forum)
            .where(Forum.heritage.contains([forum_id]))
            .order_by(Forum.order)
        )
        return await self.db_session.scalars(_limit_games(query, only_game_ids))

    async def get_subtrees(
        self, forum_ids: Collection[int], only_game_ids: Collection[int] | None = None
    ) -> ScalarResult[Forum]:
        """The given forums and every forum below them.

        ``only_game_ids`` limits game forums to those games, as in
        ``get_descendants``.
        """
        forum_ids = list(forum_ids)
        query = (
            select(Forum)
            .where(Forum.id.in_(forum_ids) | Forum.heritage.overlap(forum_ids))
            .order_by(Forum.order)
        )
        return await self.db_session.scalars(_limit_games(query, only_game_ids))

    async def update(
        self,
        forum: Forum,
        title: str | None = None,
        description: str | None = None,
    ) -> Forum:
        """Apply a partial update. ``None`` leaves a field alone; an empty
        description clears it."""
        if title is not None:
            forum.title = title
        if description is not None:
            forum.description = description or None
        await self.db_session.flush()
        return forum

    async def reorder_children(self, parent_id: int, forum_ids: list[int]) -> None:
        """Put the given children of ``parent_id`` in the given sequence.

        They swap among the order slots they already hold, so siblings left out
        (e.g. game forums a listing didn't include) keep their places.
        """
        children = list(
            await self.db_session.scalars(
                select(Forum).where(
                    Forum.parent_id == parent_id, Forum.id.in_(forum_ids)
                )
            )
        )
        if len(set(forum_ids)) != len(forum_ids) or len(children) != len(forum_ids):
            raise ValidationError(
                "Every forum must be a subforum of this forum, listed once"
            )

        children_by_id = {child.id: child for child in children}
        slots = sorted(child.order for child in children)
        for forum_id, slot in zip(forum_ids, slots):
            children_by_id[forum_id].order = slot
        await self.db_session.flush()

    async def delete(self, forum: Forum) -> None:
        """Soft-delete the forum and every forum below it, with one timestamp.

        Their threads and posts are left as they are; they're unreachable once
        their forum is gone.
        """
        await self.db_session.execute(
            update(Forum)
            .where(
                or_(Forum.id == forum.id, Forum.heritage.contains([forum.id])),
                Forum.deleted.is_(None),
            )
            .values(deleted=datetime.now(UTC))
            .execution_options(synchronize_session="fetch")
        )
        await self.db_session.flush()


def _limit_games(query: Select, only_game_ids: Collection[int] | None) -> Select:
    if only_game_ids is None:
        return query
    return query.where(Forum.game_id.is_(None) | Forum.game_id.in_(only_game_ids))
