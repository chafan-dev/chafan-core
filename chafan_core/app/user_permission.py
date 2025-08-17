from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.common import OperationType
from chafan_core.app.config import settings
from chafan_core.utils.base import ContentVisibility


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
    user_id: int,
    op_type: OperationType,
) -> bool:
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
    if get_active_site_profile(db, site=site, user_id=user_id) is None:
        return False
    if op_type == OperationType.AddSiteMember and not site.addable_member:
        return False
    return True

def article_read_allowed(
    db: Session, article: models.Article, user_id: Optional[int]) -> bool:
    if article.is_published and article.visibility == ContentVisibility.ANYONE:
        return True
    if article.author_id == user_id and user_id is not None:
        return True

    logger.info(f"User {user_id} is not allowed to read article {article.id}")
    return False

def question_read_allowed(
    cached_layer, question: models.Question, user_id: Optional[int]) -> bool:
    if not question.is_hidden:
        return True
    if user_id is not None and user_id == question.author_id:
        return True
    if user_id is None:
        return False
    # TODO we should allow superuser and admin of sites to see hidden questions
    return False


