from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ConflictException
from app.models import Report

TargetTypes = Report.TargetTypes
Reasons = Report.Reasons
Statuses = Report.Statuses


@dataclass(frozen=True)
class ReportGroup:
    """Every report (of one status) on one target, boiled down for the queue."""

    target_type: TargetTypes
    target_id: int
    status: Statuses
    count: int
    # The most urgent reason: illegal content if anyone reported it, else the
    # first report's.
    reason: Reasons
    first_reported_at: datetime
    last_reported_at: datetime
    latest_snapshot: dict


class ReportRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(
        self,
        reporter_id: int,
        target_type: TargetTypes,
        target_id: int,
        reason: Reasons,
        details: str | None,
        snapshot: dict,
    ) -> Report:
        """File a report. Raises ``ConflictException`` if the reporter already has
        one open on this target."""
        report = Report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            details=details,
            snapshot=snapshot,
        )
        try:
            # A savepoint, so the unique index rejecting a duplicate doesn't poison
            # the request's transaction.
            async with self.db_session.begin_nested():
                self.db_session.add(report)
                await self.db_session.flush()
        except IntegrityError:
            raise ConflictException("You've already reported this")
        return report

    async def count_recent(
        self, reporter_id: int, within: timedelta = timedelta(hours=1)
    ) -> int:
        """How many reports the user has filed in the last ``within``."""
        return (
            await self.db_session.scalar(
                select(func.count(Report.id)).where(
                    Report.reporter_id == reporter_id,
                    Report.created_at >= func.now() - within,
                )
            )
            or 0
        )

    def _group_query(self, status: Statuses):
        return (
            select(
                Report.target_type,
                Report.target_id,
                func.count(Report.id).label("count"),
                func.min(Report.created_at).label("first_at"),
                func.max(Report.created_at).label("last_at"),
                func.bool_or(Report.reason == Reasons.ILLEGAL_CONTENT).label("urgent"),
            )
            .where(Report.status == status)
            .group_by(Report.target_type, Report.target_id)
        )

    async def count_groups(self, status: Statuses) -> int:
        return (
            await self.db_session.scalar(
                select(func.count()).select_from(self._group_query(status).subquery())
            )
            or 0
        )

    async def get_groups(
        self, status: Statuses, page: int, limit: int
    ) -> list[ReportGroup]:
        """A page of the targets with reports of this status: illegal content
        first, then the longest waiting."""
        rows = (
            await self.db_session.execute(
                self._group_query(status)
                .order_by(
                    func.bool_or(Report.reason == Reasons.ILLEGAL_CONTENT).desc(),
                    func.min(Report.created_at).asc(),
                    Report.target_type,
                    Report.target_id,
                )
                .limit(limit)
                .offset((page - 1) * limit)
            )
        ).all()
        if not rows:
            return []

        reports = await self.db_session.scalars(
            select(Report)
            .where(
                Report.status == status,
                or_(
                    *(
                        and_(
                            Report.target_type == row.target_type,
                            Report.target_id == row.target_id,
                        )
                        for row in rows
                    )
                ),
            )
            .order_by(Report.created_at, Report.id)
        )
        by_target: dict[tuple[TargetTypes, int], list[Report]] = {}
        for report in reports:
            by_target.setdefault((report.target_type, report.target_id), []).append(
                report
            )

        groups = []
        for row in rows:
            members = by_target[(row.target_type, row.target_id)]
            urgent = next(
                (r for r in members if r.reason is Reasons.ILLEGAL_CONTENT), None
            )
            groups.append(
                ReportGroup(
                    target_type=row.target_type,
                    target_id=row.target_id,
                    status=status,
                    count=row.count,
                    reason=(urgent or members[0]).reason,
                    first_reported_at=row.first_at,
                    last_reported_at=row.last_at,
                    latest_snapshot=members[-1].snapshot,
                )
            )
        return groups

    async def get_for_target(
        self, target_type: TargetTypes, target_id: int
    ) -> list[Report]:
        """Every report on the target, oldest first, with who filed and resolved it."""
        result = await self.db_session.scalars(
            select(Report)
            .where(Report.target_type == target_type, Report.target_id == target_id)
            .options(selectinload(Report.reporter), selectinload(Report.resolver))
            .order_by(Report.created_at, Report.id)
        )
        return list(result)

    async def resolve_open(
        self,
        target_type: TargetTypes,
        target_id: int,
        resolver_id: int,
        status: Statuses,
        note: str | None,
    ) -> list[Report]:
        """Close every open report on the target; empty if there were none."""
        result = await self.db_session.scalars(
            select(Report).where(
                Report.target_type == target_type,
                Report.target_id == target_id,
                Report.status == Statuses.OPEN,
            )
        )
        reports = list(result)
        now = datetime.now(UTC)
        for report in reports:
            report.status = status
            report.resolved_by = resolver_id
            report.resolved_at = now
            report.resolution_note = note
        await self.db_session.flush()
        return reports
