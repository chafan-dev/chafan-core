import datetime
from typing import Any, List, Mapping, Optional

from sqlalchemy.orm import Session

from chafan_core.app.common import get_redis_cli
from chafan_core.app.models.audit_log import AuditLog
from chafan_core.app.schemas.audit_log import AUDIT_LOG_API_TYPE
from chafan_core.utils.base import get_uuid


def get(db: Session, id: Any) -> Optional[AuditLog]:
    return db.query(AuditLog).filter(AuditLog.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[AuditLog]:
    return db.query(AuditLog).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def get_audit_logs(
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
    db_obj = AuditLog(
        ipaddr=ipaddr,
        uuid=_get_unique_uuid(db),
        api=api,
        user_id=user_id,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        request_info=request_info,
    )
    db.add(db_obj)
    db.flush()
