from datetime import UTC, datetime, timedelta

import pytest

from app.exceptions import ConflictException
from app.models import Report
from app.repositories import ReportRepository
from tests.factories import ActivatedUserFactory

TargetTypes = Report.TargetTypes
Reasons = Report.Reasons
Statuses = Report.Statuses


class TestReportRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ReportRepository(db_session)

    @pytest.fixture
    async def reporter(self, create):
        return await create(ActivatedUserFactory)

    async def file(
        self,
        repository,
        reporter,
        target_id=1,
        reason=Reasons.SPAM,
        target_type=TargetTypes.USER,
        snapshot=None,
        age=None,
    ):
        report = await repository.create(
            reporter.id, target_type, target_id, reason, None, snapshot or {}
        )
        if age is not None:
            report.created_at = datetime.now(UTC) - age
            await repository.db_session.flush()
        return report

    async def test_one_open_report_per_reporter_and_target(
        self, repository, reporter, create
    ):
        await self.file(repository, reporter)
        other = await create(ActivatedUserFactory)

        with pytest.raises(ConflictException):
            await self.file(repository, reporter)
        # Another reporter, another target, and another target type are all fine.
        await self.file(repository, other)
        await self.file(repository, reporter, target_id=2)
        await self.file(repository, reporter, target_type=TargetTypes.GAME)

    async def test_resolving_lets_the_reporter_report_again(self, repository, reporter):
        await self.file(repository, reporter)
        await repository.resolve_open(
            TargetTypes.USER, 1, reporter.id, Statuses.DISMISSED, None
        )

        report = await self.file(repository, reporter)

        assert report.status is Statuses.OPEN

    async def test_count_recent_ignores_reports_older_than_the_window(
        self, repository, reporter
    ):
        await self.file(repository, reporter, target_id=1)
        await self.file(repository, reporter, target_id=2, age=timedelta(minutes=59))
        await self.file(repository, reporter, target_id=3, age=timedelta(hours=2))

        assert await repository.count_recent(reporter.id) == 2

    async def test_groups_put_illegal_content_first_then_oldest(
        self, repository, reporter, create
    ):
        other = await create(ActivatedUserFactory)
        await self.file(repository, reporter, target_id=1, age=timedelta(days=3))
        await self.file(repository, reporter, target_id=2, age=timedelta(days=2))
        await self.file(repository, reporter, target_id=3, age=timedelta(days=1))
        # The newest target is also reported as illegal by someone, which outranks
        # how long the others have waited.
        await self.file(repository, other, target_id=3, reason=Reasons.ILLEGAL_CONTENT)

        groups = await repository.get_groups(Statuses.OPEN, page=1, limit=10)

        assert [g.target_id for g in groups] == [3, 1, 2]
        assert await repository.count_groups(Statuses.OPEN) == 3

    async def test_group_summarises_its_reports(self, repository, reporter, create):
        other = await create(ActivatedUserFactory)
        third = await create(ActivatedUserFactory)
        await self.file(
            repository,
            reporter,
            reason=Reasons.SPAM,
            snapshot={"v": "old"},
            age=timedelta(hours=3),
        )
        await self.file(
            repository,
            other,
            reason=Reasons.ILLEGAL_CONTENT,
            snapshot={"v": "mid"},
            age=timedelta(hours=2),
        )
        newest = await self.file(
            repository,
            third,
            reason=Reasons.HARASSMENT,
            snapshot={"v": "new"},
            age=timedelta(hours=1),
        )

        (group,) = await repository.get_groups(Statuses.OPEN, page=1, limit=10)

        assert group.count == 3
        assert group.reason is Reasons.ILLEGAL_CONTENT
        assert group.latest_snapshot == {"v": "new"}
        assert group.last_reported_at == newest.created_at
        assert group.first_reported_at < group.last_reported_at

    async def test_group_reason_without_illegal_content_is_the_first_reports(
        self, repository, reporter, create
    ):
        other = await create(ActivatedUserFactory)
        await self.file(
            repository, reporter, reason=Reasons.COPYRIGHT, age=timedelta(hours=2)
        )
        await self.file(repository, other, reason=Reasons.SPAM, age=timedelta(hours=1))

        (group,) = await repository.get_groups(Statuses.OPEN, page=1, limit=10)

        assert group.reason is Reasons.COPYRIGHT

    async def test_groups_filter_by_status_and_paginate(self, repository, reporter):
        for target_id in (1, 2, 3):
            await self.file(
                repository, reporter, target_id=target_id, age=timedelta(days=target_id)
            )
        await repository.resolve_open(
            TargetTypes.USER, 3, reporter.id, Statuses.ACTIONED, "done"
        )

        page_one = await repository.get_groups(Statuses.OPEN, page=1, limit=1)
        page_two = await repository.get_groups(Statuses.OPEN, page=2, limit=1)
        actioned = await repository.get_groups(Statuses.ACTIONED, page=1, limit=10)

        assert [g.target_id for g in page_one] == [2]
        assert [g.target_id for g in page_two] == [1]
        assert [g.target_id for g in actioned] == [3]
        assert await repository.count_groups(Statuses.OPEN) == 2

    async def test_resolve_open_closes_every_open_report_on_the_target_only(
        self, repository, reporter, create
    ):
        other = await create(ActivatedUserFactory)
        staff = await create(ActivatedUserFactory)
        first = await self.file(repository, reporter)
        second = await self.file(repository, other)
        elsewhere = await self.file(repository, reporter, target_id=2)

        resolved = await repository.resolve_open(
            TargetTypes.USER, 1, staff.id, Statuses.ACTIONED, "banned"
        )

        assert len(resolved) == 2
        for report in (first, second):
            assert report.status is Statuses.ACTIONED
            assert report.resolved_by == staff.id
            assert report.resolved_at is not None
            assert report.resolution_note == "banned"
        assert elsewhere.status is Statuses.OPEN
