"""Stub persistence for image uploads.

TODO: replace with the real ``Upload`` model + migration. Until then the
endpoint works against the object store but leaves no database record, and
every upload looks new -- so re-uploading identical bytes is charged again and
``find_orphans`` / ``misdeclared_avatars`` see nothing. The real crud, model
and migration land together in the final "SQL" PR; this module is the seam that
lets the rest of the code merge first.
"""

from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy.orm import Session


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
) -> Any:
    # TODO: write an Upload row.
    return None


def exists_with_sha(db: Session, *, sha: str) -> bool:
    # TODO: query the Upload table. Until then every upload looks new.
    return False


def get_multi_by_sha(db: Session, *, sha: str) -> List[Any]:
    # TODO: return the Upload rows for `sha`.
    return []


def all_shas(db: Session) -> List[str]:
    # TODO: return every distinct sha in the Upload table.
    return []
