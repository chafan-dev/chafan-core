"""Audit log service."""

from __future__ import annotations

from typing import List, Optional

import fastapi
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.common import client_ip
from chafan_core.app.responders import misc as misc_responder


def create_audit(
    db: Session,
    *,
    api: str,
    request: Optional[fastapi.Request] = None,
    user_id: Optional[int] = None,
    request_info: Optional[dict] = None,
) -> None:
    ip = "0.0.0.0"
    if request is not None:
        ip = client_ip(request)
    if user_id is None:
        user_id = 1
    crud.audit_log.create_with_user(
        db,
        ipaddr=ip,
        user_id=user_id,
        api=api,
        request_info=request_info or {},
    )


def list_my_audit_logs(ctx) -> List[schemas.AuditLog]:
    mat = ctx.materializer
    return [
        misc_responder.audit_log_schema_from_orm(mat, audit_log)
        for audit_log in crud.audit_log.get_audit_logs(
            ctx.get_db(),
            user_id=ctx.unwrapped_principal_id(),
        )
    ]
