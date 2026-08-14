"""Image upload domain service."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from chafan_core.app import (
    coins,
    crud,
    image_sanitize,
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
