from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from app.models import Report
from app.schema_base import SchemaBase

REPORT_TEXT_MAX = 1000

ReportText = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=REPORT_TEXT_MAX)
]


class ReportInput(SchemaBase):
    target_type: Report.TargetTypes
    target_id: int
    reason: Report.Reasons
    details: ReportText | None = None

    @model_validator(mode="after")
    def details_for_other(self) -> Self:
        if not self.details:
            self.details = None
            if self.reason is Report.Reasons.OTHER:
                raise ValueError("Tell us what's wrong when the reason is other")
        return self


class ReportFiledData(SchemaBase):
    id: int
    status: Report.Statuses


class ResolveReportsInput(SchemaBase):
    status: Literal["actioned", "dismissed"]
    note: ReportText | None = None


class ReportGroupData(SchemaBase):
    target_type: Report.TargetTypes
    target_id: int
    status: Report.Statuses
    count: int
    reason: Report.Reasons
    first_reported_at: datetime
    last_reported_at: datetime
    latest_snapshot: dict


class GetReportGroupsResponse(SchemaBase):
    groups: list[ReportGroupData]
    total: int


class ReporterData(SchemaBase):
    id: int
    username: str


class ReportData(SchemaBase):
    id: int
    reporter: ReporterData
    reason: Report.Reasons
    details: str | None
    status: Report.Statuses
    created_at: datetime
    resolved_by: ReporterData | None
    resolved_at: datetime | None
    resolution_note: str | None
    snapshot: dict
    has_snapshot_file: bool


class GetTargetReportsResponse(SchemaBase):
    target_type: Report.TargetTypes
    target_id: int
    reports: list[ReportData]


class ResolvedReportsData(SchemaBase):
    resolved: int
