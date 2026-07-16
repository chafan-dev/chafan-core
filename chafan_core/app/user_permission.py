from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.common import OperationType
from chafan_core.app.model_utils import is_live_answer
from chafan_core.utils.base import ContentVisibility, HTTPException_

import logging

logger = logging.getLogger(__name__)

# TODO everything about user permission, including if they can create a site (KARMA), invite a user, write an answer, etc, should be moved into this file. 2025-07-08


def get_active_site_profile(
    db: Session, site: models.Site, user_id: int
) -> Optional[models.Profile]:
    return crud.profile.get_by_user_and_site(db, owner_id=user_id, site_id=site.id)


def user_in_site(
    db: Session,
    site: models.Site,
    user_id: Optional[int],
    op_type: OperationType,
) -> bool:
    """Site membership / public-flag check for a principal.

    Anonymous principals (user_id is None) only succeed when the site's public
    flag for the given op_type allows the operation without membership.
    """
    if op_type == OperationType.ReadSite and site.public_readable:
        return True
    if op_type == OperationType.WriteSiteAnswer and site.public_writable_answer:
        return True
    if op_type == OperationType.WriteSiteSubmission and site.public_writable_submission:
        return True
    if op_type == OperationType.WriteSiteQuestion and site.public_writable_question:
        return True
    if op_type == OperationType.WriteSiteComment and site.public_writable_comment:
        return True
    if user_id is None:
        return False
    if get_active_site_profile(db, site=site, user_id=user_id) is None:
        return False
    if op_type == OperationType.AddSiteMember and not site.addable_member:
        return False
    return True


def article_read_allowed(
    db: Session, article: models.Article, user_id: Optional[int]
) -> bool:
    if article.is_published and article.visibility == ContentVisibility.ANYONE:
        return True
    if article.author_id == user_id and user_id is not None:
        return True

    logger.info(f"User {user_id} is not allowed to read article {article.id}")
    return False


def question_read_allowed(
    ctx, question: models.Question, user_id: Optional[int]
) -> bool:
    if not question.is_hidden:
        return True
    if user_id is not None and user_id == question.author_id:
        return True
    if user_id is None:
        return False
    # TODO we should allow superuser and admin of sites to see hidden questions
    return False


def answer_read_allowed(
    db: Session, answer: models.Answer, user_id: Optional[int]
) -> bool:
    """Binary read gate for answers: allowed → full schema; denied → no payload.

    Matches the prior materialize split: authors always; live answers for site
    members / public-read; anonymous additionally requires ANYONE visibility.
    """
    if answer.is_deleted:
        return False
    if user_id is not None and user_id == answer.author_id:
        return True
    if not is_live_answer(answer):
        return False
    if user_id is None:
        if answer.visibility != ContentVisibility.ANYONE:
            return False
        return bool(answer.site.public_readable)
    return user_in_site(
        db, site=answer.site, user_id=user_id, op_type=OperationType.ReadSite
    )


def can_read_answer(db: Session, *, answer: models.Answer, principal_id: int) -> bool:
    """Stricter gift/reward check: live answer readable by giver principal."""
    if answer.is_deleted:
        return False
    if principal_id == answer.author_id:
        return True
    if not is_live_answer(answer):
        return False
    return user_in_site(
        db, site=answer.site, user_id=principal_id, op_type=OperationType.ReadSite
    )


def visitor_can_read_answer(*, answer: models.Answer) -> bool:
    if not is_live_answer(answer):
        return False
    if answer.visibility != ContentVisibility.ANYONE:
        return False
    return bool(answer.site.public_readable)


def check_user_in_site(
    db: Session, *, site: models.Site, user_id: int, op_type: OperationType
) -> None:
    if not user_in_site(db, site=site, user_id=user_id, op_type=op_type):
        raise HTTPException_(
            status_code=400,
            detail="Current user is not allowed in this site.",
        )


def check_user_in_channel(current_user: models.User, channel: models.Channel) -> None:
    if (
        current_user not in channel.members
        and current_user is not channel.admin
        and current_user is not channel.private_with_user
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
