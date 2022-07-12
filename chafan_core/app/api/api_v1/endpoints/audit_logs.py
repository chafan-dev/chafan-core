from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer

router = APIRouter()


@router.get("/", response_model=List[schemas.AuditLog])
def get_audit_logs(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    return [
        cached_layer.materializer.audit_log_schema_from_orm(audit_log)
        for audit_log in crud.audit_log.get_audit_logs(
            cached_layer.get_db(),
            user_id=cached_layer.unwrapped_principal_id(),
        )
    ]
