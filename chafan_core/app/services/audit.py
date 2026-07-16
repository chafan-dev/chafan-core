"""Audit log service."""

from __future__ import annotations

from typing import Optional

import fastapi
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.common import client_ip


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
