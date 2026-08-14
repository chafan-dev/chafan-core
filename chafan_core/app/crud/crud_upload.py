import datetime
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from chafan_core.app.models.upload import Upload


def create(
    db: Session,
    *,
    uploader_id: int,
    sha256: str,
    content_type: str,
    size_bytes: int,
    purpose: str,
    storage_bucket: str,
    original_filename: Optional[str] = None,
) -> Upload:
    upload = Upload(
        uploader_id=uploader_id,
        sha256=sha256,
        content_type=content_type,
        size_bytes=size_bytes,
        original_filename=original_filename,
        purpose=purpose,
        storage_bucket=storage_bucket,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    db.add(upload)
    db.flush()
    db.refresh(upload)
    return upload


def exists_with_sha(db: Session, *, sha: str) -> bool:
    return db.query(Upload).filter(Upload.sha256 == sha).first() is not None


def get_multi_by_sha(db: Session, *, sha: str) -> List[Upload]:
    return db.query(Upload).filter(Upload.sha256 == sha).all()


def all_shas(db: Session) -> List[str]:
    return [row[0] for row in db.query(Upload.sha256).distinct().all()]


def get(db: Session, id: Any) -> Optional[Upload]:
    return db.query(Upload).filter(Upload.id == id).first()
