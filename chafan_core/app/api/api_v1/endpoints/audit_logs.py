from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import audit as audit_service

router = APIRouter()


@router.get("/", response_model=List[schemas.AuditLog])
def get_audit_logs(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return audit_service.list_my_audit_logs(ctx)
