import datetime
from typing import Any, List, Optional

from sqlalchemy import text
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


def advisory_key(sha: str) -> int:
    """The bigint an advisory lock on ``sha`` uses.

    Postgres advisory locks key on a signed 64-bit integer, so only part of the
    sha fits: 15 hex digits is 60 bits, comfortably inside the positive range.
    A collision between two different shas is harmless -- it costs one upload a
    needless wait, never correctness -- so truncation is fine here in a way it
    would not be for the content address itself.
    """
    return int(sha[:15], 16)


def lock_sha(db: Session, *, sha: str) -> None:
    """Serialize the check-then-charge for ``sha`` against concurrent uploads.

    ``exists_with_sha`` followed by ``create`` is not atomic, and ``sha256`` is
    deliberately not unique (see the model docstring), so nothing at the schema
    level collapses a duplicate. Two requests carrying the same *new* bytes
    therefore both read the sha as absent, both store the object -- idempotent,
    same key -- and both deduct UPLOAD_IMAGE_COST. The user pays twice for one
    object, and every upload afterwards is correctly free, which is what makes
    it easy to miss.

    The lock is transaction-scoped, and a request is one transaction committed
    by ``get_request_context``, so it is held across the check, the charge and
    the insert. The second request waits here and, once the first commits, sees
    the row and takes the free path.
    """
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": advisory_key(sha)})


def exists_with_sha(db: Session, *, sha: str) -> bool:
    return db.query(Upload).filter(Upload.sha256 == sha).first() is not None


def get_multi_by_sha(db: Session, *, sha: str) -> List[Upload]:
    return db.query(Upload).filter(Upload.sha256 == sha).all()


def all_shas(db: Session) -> List[str]:
    return [row[0] for row in db.query(Upload.sha256).distinct().all()]


def get(db: Session, id: Any) -> Optional[Upload]:
    return db.query(Upload).filter(Upload.id == id).first()
