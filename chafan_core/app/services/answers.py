"""Answer domain service."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud


def delete_answer(
    db: Session, *, uuid: str, principal_id: Optional[int]
) -> Optional[str]:
    """Delete answer forever. Returns error message or None on success."""
    answer = crud.answer.get_by_uuid(db, uuid=uuid)
    if answer is None:
        return "The answer doesn't exist in the system."
    if answer.author_id != principal_id:
        return "Unauthorized."
    crud.answer.delete_forever(db, answer=answer)
    return None
