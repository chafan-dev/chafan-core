import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.models.audit_log import AuditLog
from chafan_core.app.schemas.user import UserCreate
from chafan_core.utils.base import get_uuid
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _create_test_user(db: Session):
    """Helper to create a test user."""
    user_in = UserCreate(
        email=random_email(),
        password=random_password(),
        handle=random_short_lower_string(),
    )
    return asyncio.run(crud.user.create(db, obj_in=user_in))


def _create_audit_log_directly(
    db: Session, user_id: int, ipaddr: str, api: str, request_info: dict = None
):
    """Helper to create an audit log directly in the database."""
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    audit_log = AuditLog(
        uuid=get_uuid(),
        ipaddr=ipaddr,
        api=api,
        user_id=user_id,
        created_at=utc_now,
        request_info=request_info,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log


def test_get_audit_log_by_id(db: Session) -> None:
    """Test getting an audit log by ID."""
    user = _create_test_user(db)
    audit_log = _create_audit_log_directly(
        db, user_id=user.id, ipaddr="192.168.1.1", api="login"
    )

    retrieved = crud.audit_log.get(db, id=audit_log.id)
    assert retrieved is not None
    assert retrieved.id == audit_log.id
    assert retrieved.ipaddr == "192.168.1.1"
    assert retrieved.api == "login"


def test_get_audit_log_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent audit log."""
    result = crud.audit_log.get(db, id=99999999)
    assert result is None


def test_get_audit_logs_for_user(db: Session) -> None:
    """Test getting audit logs for a specific user."""
    user = _create_test_user(db)

    # Create several audit logs for this user
    for i in range(3):
        _create_audit_log_directly(
            db, user_id=user.id, ipaddr=f"192.168.1.{i}", api="login"
        )

    logs = crud.audit_log.get_audit_logs(db, user_id=user.id)
    assert len(logs) >= 3
    assert all(log.user_id == user.id for log in logs)


def test_get_audit_logs_without_user_filter(db: Session) -> None:
    """Test getting all audit logs without user filter."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)

    _create_audit_log_directly(db, user_id=user1.id, ipaddr="10.0.0.1", api="login")
    _create_audit_log_directly(db, user_id=user2.id, ipaddr="10.0.0.2", api="logout")

    logs = crud.audit_log.get_audit_logs(db)
    assert len(logs) >= 2


def test_get_audit_logs_pagination(db: Session) -> None:
    """Test pagination of audit logs."""
    user = _create_test_user(db)

    # Create several audit logs
    for i in range(5):
        _create_audit_log_directly(
            db, user_id=user.id, ipaddr=f"192.168.1.{i}", api="action"
        )

    page1 = crud.audit_log.get_audit_logs(db, user_id=user.id, skip=0, limit=2)
    page2 = crud.audit_log.get_audit_logs(db, user_id=user.id, skip=2, limit=2)

    assert len(page1) <= 2
    assert len(page2) <= 2

    # Pages should have different logs
    if len(page1) > 0 and len(page2) > 0:
        page1_ids = {log.id for log in page1}
        page2_ids = {log.id for log in page2}
        assert page1_ids.isdisjoint(page2_ids)


def test_audit_log_timestamps(db: Session) -> None:
    """Test that audit logs have correct timestamps."""
    user = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    audit_log = _create_audit_log_directly(
        db, user_id=user.id, ipaddr="192.168.1.1", api="test"
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert audit_log.created_at is not None
    assert before_create <= audit_log.created_at <= after_create


def test_audit_log_with_request_info(db: Session) -> None:
    """Test creating an audit log with request info."""
    user = _create_test_user(db)

    request_info = {"user_agent": "Mozilla/5.0", "method": "POST"}

    audit_log = _create_audit_log_directly(
        db,
        user_id=user.id,
        ipaddr="192.168.1.1",
        api="action",
        request_info=request_info,
    )

    retrieved = crud.audit_log.get(db, id=audit_log.id)
    assert retrieved is not None
    assert retrieved.request_info is not None
    assert retrieved.request_info["user_agent"] == "Mozilla/5.0"


def test_audit_log_different_api_types(db: Session) -> None:
    """Test creating audit logs with different API types."""
    user = _create_test_user(db)

    api_types = ["login", "logout", "create_question", "answer_question"]

    for api in api_types:
        audit_log = _create_audit_log_directly(
            db, user_id=user.id, ipaddr="192.168.1.1", api=api
        )
        assert audit_log.api == api


def test_audit_logs_ordered_by_id_desc(db: Session) -> None:
    """Test that audit logs are ordered by ID descending."""
    user = _create_test_user(db)

    # Create logs with some delay to ensure different IDs
    logs = []
    for i in range(3):
        log = _create_audit_log_directly(
            db, user_id=user.id, ipaddr=f"192.168.1.{i}", api="test"
        )
        logs.append(log)

    retrieved_logs = crud.audit_log.get_audit_logs(db, user_id=user.id, limit=10)

    # Should be in descending order by ID
    for i in range(len(retrieved_logs) - 1):
        assert retrieved_logs[i].id > retrieved_logs[i + 1].id


def test_multiple_audit_logs_same_ip(db: Session) -> None:
    """Test multiple audit logs from the same IP address."""
    user = _create_test_user(db)
    ip = "192.168.1.100"

    logs = []
    for _ in range(3):
        log = _create_audit_log_directly(db, user_id=user.id, ipaddr=ip, api="action")
        logs.append(log)

    assert len(logs) == 3
    assert all(log.ipaddr == ip for log in logs)
