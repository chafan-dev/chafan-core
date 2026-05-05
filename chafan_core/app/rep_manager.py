"""
Centralized karma + coin mutation routing.

All karma rule constants and all coin mutations live here. Direct writes to
User.karma and User.remaining_coins outside this module are not allowed.

Profile.karma (per-site karma) is frozen — the column still exists in the DB
but is no longer written or read by application code.

Coins are anti-spam, not currency: drift is tolerable, atomicity is not a goal.
"""
from typing import List

from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.model_utils import is_live_answer, is_live_article
from chafan_core.app.schemas.user import (
    UserEducationExperienceInternal,
    UserWorkExperienceInternal,
)
from pydantic.tools import parse_obj_as

import logging
logger = logging.getLogger(__name__)


# Karma constants — used by both incremental award_* functions (forward-looking)
# and by compute_karma below. Single source of truth.
ANSWER_CREATE_KARMA = 10
ANSWER_UPVOTE_KARMA = 10
QUESTION_CREATE_KARMA = 5
QUESTION_UPVOTE_KARMA = 10
SUBMISSION_CREATE_KARMA = 1
SUBMISSION_UPVOTE_KARMA = 2
ARTICLE_CREATE_KARMA = 5
ARTICLE_UPVOTE_KARMA = 10
COMMENT_CREATE_KARMA = 2
PROFILE_FIELD_KARMA = 2
EXPERIENCE_KARMA_PER_ITEM = 2
EXPERIENCE_KARMA_MAX_ITEMS = 5


# ---------------------------------------------------------------------------
# Event functions (forward-looking).
#
# Today, karma is fully recomputed by compute_karma() from authoritative source
# state — there are no incremental User.karma writes anywhere in the codebase.
# These award_*/revoke_* functions exist as the contract for future incremental
# updates and to give callers a single import surface.
# ---------------------------------------------------------------------------

def award_question_created(db: Session, user: models.User, question: models.Question) -> None:
    pass

def award_submission_created(db: Session, user: models.User, submission: models.Submission) -> None:
    pass

def award_submission_suggestion_created(
    db: Session, user: models.User, ss: models.SubmissionSuggestion
) -> None:
    pass

def award_submission_suggestion_accepted(
    db: Session, user: models.User, ss: models.SubmissionSuggestion
) -> None:
    pass

def award_answer_suggest_created(
    db: Session, user: models.User, ase: models.AnswerSuggestEdit
) -> None:
    pass

def award_answer_suggest_accepted(
    db: Session, user: models.User, ase: models.AnswerSuggestEdit
) -> None:
    pass

def award_article_created(db: Session, user: models.User, article: models.Article) -> None:
    pass


# ---------------------------------------------------------------------------
# Coin mutations. All coin changes route through these two functions.
# ---------------------------------------------------------------------------

def deduct_coins(db: Session, user: models.User, amount: int, reason: str) -> None:
    user.remaining_coins -= amount
    db.add(user)
    logger.info(f"deduct_coins user_id={user.id} amount={amount} reason={reason}")

def award_coins(db: Session, user: models.User, amount: int, reason: str) -> None:
    user.remaining_coins += amount
    db.add(user)
    logger.info(f"award_coins user_id={user.id} amount={amount} reason={reason}")


# ---------------------------------------------------------------------------
# Authoritative karma recomputation.
# ---------------------------------------------------------------------------

def set_karma(db: Session, user: models.User, value: int) -> None:
    """Authoritative writer for User.karma — only used by refresh_karmas."""
    user.karma = value
    db.add(user)


def compute_karma(db: Session, user: models.User) -> int:
    """Recompute total karma from authoritative source state."""
    karma = 0
    if user.work_experiences:
        karma += min(
            len(parse_obj_as(List[UserWorkExperienceInternal], user.work_experiences)),
            EXPERIENCE_KARMA_MAX_ITEMS,
        ) * EXPERIENCE_KARMA_PER_ITEM
    if user.education_experiences:
        karma += min(
            len(parse_obj_as(List[UserEducationExperienceInternal], user.education_experiences)),
            EXPERIENCE_KARMA_MAX_ITEMS,
        ) * EXPERIENCE_KARMA_PER_ITEM
    profile_fields = [
        user.full_name,
        user.github_username,
        user.github_username,
        user.twitter_username,
        user.linkedin_url,
        user.homepage_url,
        user.zhihu_url,
        user.avatar_url,
        user.gif_avatar_url,
        user.personal_introduction,
    ]
    for item in profile_fields:
        if item:
            karma += PROFILE_FIELD_KARMA
    for a in user.answers:
        if is_live_answer(a):
            karma += ANSWER_CREATE_KARMA + a.upvotes_count * ANSWER_UPVOTE_KARMA
    for q in user.questions:
        karma += QUESTION_CREATE_KARMA + q.upvotes_count * QUESTION_UPVOTE_KARMA
    for s in user.submissions:
        if not s.is_hidden:
            karma += SUBMISSION_CREATE_KARMA + s.upvotes_count * SUBMISSION_UPVOTE_KARMA
    for article in user.articles:
        if is_live_article(article):
            karma += ARTICLE_CREATE_KARMA + article.upvotes_count * ARTICLE_UPVOTE_KARMA
    for _ in user.comments:
        karma += COMMENT_CREATE_KARMA
    return karma
