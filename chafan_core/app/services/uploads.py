"""Image upload domain service."""

from __future__ import annotations

import hashlib
import logging
import re
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
from chafan_core.app.common import MAX_UPLOAD_BYTES, report_msg
from chafan_core.app.config import settings
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.constants import upload_purpose_T

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


def upload_image(
    ctx, *, file, file_size: int, purpose: upload_purpose_T
) -> schemas.UploadedImage:
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

    # Everything from here to the insert has to be one critical section per
    # sha, or two concurrent uploads of the same new bytes both pay for it.
    crud.upload.lock_sha(db, sha=sha)
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

# Every column that can hold the URL of an uploaded image. Bodies are the
# obvious ones. The two avatar columns matter just as much: a purpose="avatar"
# upload is never embedded in anyone's body, so without them every avatar ever
# uploaded reads as an orphan -- and orphans are the input to any future
# garbage collection.
_REFERENCE_COLUMNS = [
    (models.Article, "body", "article"),
    (models.Article, "body_draft", "article"),
    (models.ArticleArchive, "body", "article_archive"),
    (models.Answer, "body", "answer"),
    (models.Answer, "body_draft", "answer"),
    (models.Archive, "body", "answer_archive"),
    (models.Comment, "body", "comment"),
    (models.Question, "description", "question"),
    (models.QuestionArchive, "description", "question_archive"),
    (models.Submission, "description", "submission"),
    (models.SubmissionArchive, "description", "submission_archive"),
    (models.User, "avatar_url", "user_avatar"),
    (models.User, "gif_avatar_url", "user_gif_avatar"),
]


def find_usages(db: Session, *, sha: str) -> List[str]:
    """Locations (``table:id``) that reference ``sha``.

    The public URL embeds the sha, so a ``LIKE`` hit is exact.
    """
    usages: List[str] = []
    for model, column, label in _REFERENCE_COLUMNS:
        col = getattr(model, column)
        for (id_,) in db.query(model.id).filter(col.like(f"%{sha}%")).all():
            usages.append(f"{label}:{id_}")
    return usages


def find_orphans(db: Session) -> List[models.Upload]:
    """Uploads whose sha appears in no body or archive text. Report only."""
    orphans: List[models.Upload] = []
    for sha in crud.upload.all_shas(db):
        if not find_usages(db, sha=sha):
            orphans.extend(crud.upload.get_multi_by_sha(db, sha=sha))
    return orphans


# ---------------------------------------------------------------------------
# Avatar-misuse detection.
#
# ``purpose`` is client-supplied, so the karma gate on ``purpose="figure"`` is
# bypassable by a user sending ``purpose="avatar"`` and pasting the URL into an
# article by hand. Prevention was never available; detection is. This runs at
# article *read* time, so no write hook can be forgotten: if a body embeds an
# image its author only ever declared an avatar, someone lied, and it is
# reported once (deduplicated in Redis) and swallowed on any failure.
# ---------------------------------------------------------------------------

_SHA_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
_MISDECLARED_TTL_SECONDS = 60 * 60 * 24 * 90


def _shas_in_body(body: str) -> List[str]:
    return list(dict.fromkeys(_SHA_RE.findall(body or "")))


def misdeclared_avatars(ctx, *, author_id: int, body: str) -> List[str]:
    """Shas embedded in ``body`` that ``author_id`` only ever uploaded as an avatar.

    A sha the author legitimately uploaded as a figure is fine even if someone
    else used it as an avatar; a sha the author never uploaded at all is not
    this check's business.
    """
    db = ctx.get_db()
    reported: List[str] = []
    for sha in _shas_in_body(body):
        purposes = {
            row.purpose
            for row in crud.upload.get_multi_by_sha(db, sha=sha)
            if row.uploader_id == author_id
        }
        if "avatar" in purposes and "figure" not in purposes:
            reported.append(sha)
    return reported


def check_article_for_misdeclared_avatars(ctx, *, article) -> None:
    """Advisory detection on an article read; must never break the page."""
    try:
        shas = misdeclared_avatars(
            ctx, author_id=article.author_id, body=article.body
        )
    except Exception:
        logger.exception(
            "misdeclared-avatar detection failed for article %s", article.uuid
        )
        return
    if not shas:
        return
    redis = ctx.get_redis()
    for sha in shas:
        key = f"upload:misdeclared-avatar:{article.id}:{sha}"
        try:
            newly_reported = redis.set(
                key, "1", nx=True, ex=_MISDECLARED_TTL_SECONDS
            )
        except Exception:
            logger.exception(
                "misdeclared-avatar dedupe failed for article %s", article.uuid
            )
            continue
        if newly_reported:
            report_msg(
                f"misdeclared avatar: article={article.uuid} "
                f"author_id={article.author_id} sha={sha}"
            )
