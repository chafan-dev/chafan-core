from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext

router = APIRouter()


@router.get("/", response_model=List[schemas.AuditLog])
def get_audit_logs(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    cached_layer = deps.cached_layer_from_context(ctx)
    return [
        cached_layer.materializer.audit_log_schema_from_orm(audit_log)
        for audit_log in crud.audit_log.get_audit_logs(
            cached_layer.get_db(),
            user_id=cached_layer.unwrapped_principal_id(),
        )
    ]
