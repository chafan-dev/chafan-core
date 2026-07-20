from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import reports as reports_service

router = APIRouter()


@router.post("/", response_model=schemas.Report)
def create_report(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    report_in: schemas.ReportCreate,
) -> Any:
    """
    Create new report authored by the current active user in one of the belonging sites.
    """
    return reports_service.create_report(ctx, report_in=report_in)
