from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Upload(Base):
    """One row per *accepted* upload; the bucket holds one object per sha256.

    The two non-obvious columns:

      * ``sha256`` is deliberately NOT unique. The bucket stores one object per
        sha; this table records one row per accepted upload, so a free re-upload
        still leaves an audit trail and the second person to upload the same
        bytes is not erased.
      * ``storage_bucket`` records which bucket holds those bytes, so a future
        vendor migration is a verifiable list rather than a guess.
    """

    id = Column(Integer, primary_key=True, index=True)
    uploader_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    uploader: Optional["User"] = relationship("User", back_populates="uploads")  # type: ignore
    sha256 = Column(String, nullable=False, index=True)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)  # after sanitizing
    original_filename = Column(String)
    purpose = Column(String, nullable=False)  # "figure" | "avatar"
    storage_bucket = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
