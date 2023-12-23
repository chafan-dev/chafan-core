import datetime
from typing import Any, List, Mapping, Optional

from sqlalchemy.orm import Session

from chafan_core.app.common import get_redis_cli
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.audit_log import AuditLog
from chafan_core.app.schemas.audit_log import (
    AUDIT_LOG_API_TYPE,
    AuditLogCreate,
    AuditLogUpdate,
)


class CRUDAuditLog(CRUDBase[AuditLog, AuditLogCreate, AuditLogUpdate]):
    def get_audit_logs(
        self,
        db: Session,
        *,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        query = db.query(AuditLog)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.order_by(AuditLog.id.desc()).offset(skip).limit(limit).all()

    def create_with_user(
        self,
        db: Session,
        *,
        ipaddr: str,
        api: AUDIT_LOG_API_TYPE,
        user_id: int,
        request_info: Optional[Mapping[str, Any]] = None,
    ) -> None:
        redis = get_redis_cli()
        key = f"chafan:audit-log:{ipaddr}:{api}{user_id}"
        value = redis.get(key)
        if value is not None:
            return
        redis.set(key, "true", ex=datetime.timedelta(hours=1))
        db_obj = self.model(
            ipaddr=ipaddr,
            uuid=self.get_unique_uuid(db),
            api=api,
            user_id=user_id,
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            request_info=request_info,
        )
        db.add(db_obj)
        db.commit()


audit_log = CRUDAuditLog(AuditLog)
