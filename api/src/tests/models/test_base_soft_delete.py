from datetime import UTC, datetime

from sqlalchemy import select

from app.models.genre import Genre


class TestSoftDeleteFiltering:
    async def test_deleted_row_excluded_by_default(
        self, db_session, wrap_in_savepoint
    ):
        alive = Genre(genre="Alive")
        dead = Genre(genre="Dead", deleted=datetime.now(UTC))
        db_session.add_all([alive, dead])
        await db_session.flush()

        result = await db_session.scalars(select(Genre))
        names = {g.genre for g in result}

        assert names == {"Alive"}

    async def test_skip_filter_includes_deleted_row(
        self, db_session, wrap_in_savepoint
    ):
        alive = Genre(genre="Alive")
        dead = Genre(genre="Dead", deleted=datetime.now(UTC))
        db_session.add_all([alive, dead])
        await db_session.flush()

        stmt = select(Genre).execution_options(skip_filter=True)
        result = await db_session.scalars(stmt)
        names = {g.genre for g in result}

        assert names == {"Alive", "Dead"}

    async def test_get_by_pk_is_not_filtered(self, db_session, wrap_in_savepoint):
        """Session.get() does not go through do_orm_execute's is_select branch,
        so it bypasses the soft-delete filter entirely (even without skip_filter).
        """
        dead = Genre(genre="Dead", deleted=datetime.now(UTC))
        db_session.add(dead)
        await db_session.flush()

        found = await db_session.get(Genre, dead.id)

        assert found is not None
        assert found.id == dead.id
