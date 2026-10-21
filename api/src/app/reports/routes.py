from pathlib import Path

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.helpers.decorators import requires
from app.helpers.functions import error_response
from app.middleware import Principal
from app.models import Report
from app.repositories import ReportRepository
from app.reports import schemas
from app.reports.functions import (
    build_report_data,
    load_target,
    remove_image,
    snapshot_image,
)
from app.schemas import ErrorItem

reports = APIRouter(prefix="/reports")

REPORTS_PER_HOUR = 10
REPORT_GROUPS_PER_PAGE = 25
IMAGE_REMOVED_NOTE = "Image removed"
SNAPSHOT_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@reports.post(
    "", response_model=schemas.ReportFiledData, status_code=status.HTTP_201_CREATED
)
async def create_report(
    data: schemas.ReportInput, db_session: DBSessionDependency, principal: Principal
):
    report_repository = ReportRepository(db_session)
    if await report_repository.count_recent(principal.id) >= REPORTS_PER_HOUR:
        return error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            errors=[
                ErrorItem(
                    code="rate_limited",
                    detail="You've filed several reports recently. Please try again later.",
                )
            ],
        )

    target = await load_target(db_session, principal, data.target_type, data.target_id)
    report = await report_repository.create(
        principal.id,
        data.target_type,
        data.target_id,
        data.reason,
        data.details,
        target.snapshot,
    )
    snapshot_image(report, target)
    await db_session.flush()
    return report


@reports.get("", response_model=schemas.GetReportGroupsResponse)
@requires("manage_reports")
async def get_report_groups(
    db_session: DBSessionDependency,
    status_filter: Report.Statuses = Query(Report.Statuses.OPEN, alias="status"),
    page: int = 1,
):
    """The reported targets of one status, most urgent first."""
    if page < 1:
        page = 1
    report_repository = ReportRepository(db_session)
    return {
        "groups": await report_repository.get_groups(
            status_filter, page, REPORT_GROUPS_PER_PAGE
        ),
        "total": await report_repository.count_groups(status_filter),
    }


@reports.get("/{report_id}/snapshot-file")
@requires("manage_reports")
async def get_snapshot_file(report_id: int, db_session: DBSessionDependency):
    """The quarantined copy of a reported image (nginx doesn't serve quarantine).

    Declared before ``/{target_type}/{target_id}``, which has the same segment
    count and would otherwise try to parse ``snapshot-file`` as an id.
    """
    report = await ReportRepository(db_session).get(report_id)
    if report is None or report.snapshot_file is None:
        raise NotFoundException("No snapshot image for that report")
    root = Path(configs.QUARANTINE_DIR).resolve()
    path = (root / report.snapshot_file).resolve()
    media_type = SNAPSHOT_MEDIA_TYPES.get(path.suffix.lower())
    if not path.is_relative_to(root) or media_type is None or not path.is_file():
        raise NotFoundException("No snapshot image for that report")
    return FileResponse(
        path,
        media_type=media_type,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@reports.get(
    "/{target_type}/{target_id}", response_model=schemas.GetTargetReportsResponse
)
@requires("manage_reports")
async def get_target_reports(
    target_type: Report.TargetTypes, target_id: int, db_session: DBSessionDependency
):
    found = await ReportRepository(db_session).get_for_target(target_type, target_id)
    if not found:
        raise NotFoundException("No reports for that target")
    return {
        "target_type": target_type,
        "target_id": target_id,
        "reports": [build_report_data(report) for report in found],
    }


@reports.post(
    "/{target_type}/{target_id}/resolve", response_model=schemas.ResolvedReportsData
)
@requires("manage_reports")
async def resolve_reports(
    target_type: Report.TargetTypes,
    target_id: int,
    data: schemas.ResolveReportsInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Close every open report on the target at once."""
    resolved = await ReportRepository(db_session).resolve_open(
        target_type,
        target_id,
        principal.id,
        Report.Statuses(data.status),
        data.note,
    )
    if not resolved:
        raise NotFoundException("No open reports for that target")
    return {"resolved": len(resolved)}


@reports.post(
    "/{target_type}/{target_id}/remove-image", status_code=status.HTTP_204_NO_CONTENT
)
@requires("manage_reports")
async def remove_reported_image(
    target_type: Report.TargetTypes,
    target_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Take the image out of use (the file is kept in quarantine) and mark its
    open reports actioned."""
    await remove_image(db_session, principal, target_type, target_id)
    await ReportRepository(db_session).resolve_open(
        target_type,
        target_id,
        principal.id,
        Report.Statuses.ACTIONED,
        IMAGE_REMOVED_NOTE,
    )
