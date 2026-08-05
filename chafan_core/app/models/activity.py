from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Activity(Base):
    """A published event: what happened, and where it may be seen.

    Subject-oriented, carries the payload. See docs/glossary.md.
    """

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), index=True)
    site: Optional["Site"] = relationship("Site", foreign_keys=[site_id])  # type: ignore
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    event_json = Column(String, nullable=False)

    # Who the event is about, lifted out of event_json so subject timelines are
    # expressible in SQL. Nullable for the two-phase deploy (rows written before
    # this column existed) and for historical rows a backfill cannot resolve --
    # not because any verb lacks a subject. See
    # docs/proposals/2026-08-04-activity-feed-reassignment.md.
    subject_user_id = Column(Integer, ForeignKey("user.id"), index=True, nullable=True)
    subject_user: Optional["User"] = relationship("User", foreign_keys=[subject_user_id])  # type: ignore
