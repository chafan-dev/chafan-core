"""Image upload domain service."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, List

from sqlalchemy.orm import Session

from chafan_core.app import (
    coins,
    crud,
    image_sanitize,
    models,
    object_storage,
    rules,
    schemas,
)
from chafan_core.app.common import MAX_UPLOAD_BYTES
from chafan_core.app.config import settings
from chafan_core.utils.base import HTTPException_

logger = logging.getLogger(__name__)

_READ_CHUNK = 1024 * 1024


def _read_bytes(file: Any) -> bytes:
    """Read the upload fully into memory, hard-stopping at MAX_UPLOAD_BYTES.

    The client's Content-Length is validated separately (valid_content_length),
    but that header is client-supplied; the read loop must not trust it.
    """
    buf = bytearray()
    while True:
        chunk = file.file.read(_READ_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_UPLOAD_BYTES:
            raise HTTPException_(status_code=413, detail="File too large.")
    return bytes(buf)


def upload_image(ctx, *, file, file_size: int, purpose: str) -> schemas.UploadedImage:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()

    if purpose == "figure" and (current_user.karma or 0) < rules.MIN_KARMA_UPLOAD_IMAGE:
        raise HTTPException_(
            status_code=403,
            detail=(
                f"Uploading a figure requires {rules.MIN_KARMA_UPLOAD_IMAGE} karma."
            ),
        )

    raw = _read_bytes(file)
    try:
        clean, content_type = image_sanitize.sanitize(raw)
    except image_sanitize.UnsupportedImage as exc:
        raise HTTPException_(
            status_code=415, detail="Unsupported or invalid image."
        ) from exc
    sha = hashlib.sha256(clean).hexdigest()

    is_new = not crud.upload.exists_with_sha(db, sha=sha)
    if is_new:
        if current_user.remaining_coins < rules.UPLOAD_IMAGE_COST:
            raise HTTPException_(status_code=400, detail="Insufficient coins.")
        # PUT before the row, never the reverse: a row pointing at bytes that
        # were never stored is worse than bytes with no row. A crash between
        # the two re-charges the next upload of those bytes and stores nothing
        # extra, which is the acceptable direction to fail.
        object_storage.put_image(sha=sha, content_type=content_type, data=clean)
        coins.deduct_coins(db, current_user, rules.UPLOAD_IMAGE_COST, "image_upload")

    # Written in both branches: a free re-upload still leaves an audit trail.
    crud.upload.create(
        db,
        uploader_id=current_user.id,
        sha256=sha,
        content_type=content_type,
        size_bytes=len(clean),
        original_filename=file.filename,
        purpose=purpose,
        storage_bucket=settings.UPLOADS_S3_BUCKET,
    )
    return schemas.UploadedImage(url=object_storage.public_url(sha, content_type))


# ---------------------------------------------------------------------------
# Usage accounting: computed, not stored.
#
# delete_forever overwrites body, body_draft and every archive row with
# "[DELETED]", so the references leave the database and a scan of bodies gives
# the correct answer with no join table to maintain. Nothing here deletes.
# ---------------------------------------------------------------------------

_BODY_COLUMNS = [
    (models.Article, "body", "article"),
    (models.Article, "body_draft", "article"),
    (models.ArticleArchive, "body", "article_archive"),
    (models.Answer, "body", "answer"),
    (models.Answer, "body_draft", "answer"),
    (models.Archive, "body", "answer_archive"),
    (models.Comment, "body", "comment"),
    (models.Submission, "description", "submission"),
    (models.SubmissionArchive, "description", "submission_archive"),
]


def find_usages(db: Session, *, sha: str) -> List[str]:
    """Locations (``table:id``) whose body text embeds ``sha``.

    The public URL embeds the sha, so a ``LIKE`` hit is exact.
    """
    usages: List[str] = []
    for model, column, label in _BODY_COLUMNS:
        col = getattr(model, column)
        for (id_,) in db.query(model.id).filter(col.like(f"%{sha}%")).all():
            usages.append(f"{label}:{id_}")
    return usages


def find_orphans(db: Session) -> List[Any]:
    """Uploads whose sha appears in no body or archive text. Report only.

    Returns nothing until the Upload table lands (``crud.upload`` is stubbed);
    typed ``Any`` so the real model can arrive later without touching this.
    """
    orphans: List[Any] = []
    for sha in crud.upload.all_shas(db):
        if not find_usages(db, sha=sha):
            orphans.extend(crud.upload.get_multi_by_sha(db, sha=sha))
    return orphans
