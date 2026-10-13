from datetime import UTC, datetime

from sqlalchemy import select

from app.models.genre import Genre


class TestSoftDeleteFiltering:
    async def test_deleted_row_excluded_unless_skip_filter(
        self, db_session, wrap_in_savepoint
    ):
        alive = Genre(genre="Alive")
        dead = Genre(genre="Dead", deleted=datetime.now(UTC))
        db_session.add_all([alive, dead])
        await db_session.flush()

        default = await db_session.scalars(select(Genre))
        skipped = await db_session.scalars(
            select(Genre).execution_options(skip_filter=True)
        )

        assert {g.genre for g in default} == {"Alive"}
        assert {g.genre for g in skipped} == {"Alive", "Dead"}

    async def test_get_by_pk_is_filtered_unless_skip_filter(
        self, db_session, wrap_in_savepoint
    ):
        """Session.get() does go through the soft-delete filter once the row is
        no longer in the identity map (it only looks unfiltered while the
        instance is still identity-mapped)."""
        dead = Genre(genre="Dead", deleted=datetime.now(UTC))
        db_session.add(dead)
        await db_session.flush()
        dead_id = dead.id
        # Drop the identity-mapped instance so get() must hit the database.
        db_session.expunge_all()

        assert await db_session.get(Genre, dead_id) is None
        found = await db_session.get(
            Genre, dead_id, execution_options={"skip_filter": True}
        )
        assert found is not None
        assert found.id == dead_id
