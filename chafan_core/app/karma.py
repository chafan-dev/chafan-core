"""Karma: the single place that changes `User.karma`.

The numbers live in `rules.py`; this module only applies them. It sits next to
`coins.py` rather than under `services/` so that `crud` can import it without
an upward import -- karma changes at the same moments `upvotes_count` does,
and that bookkeeping lives in crud.

How it works. Every piece of content is worth some karma to its author right
now -- see `contribution()`. Callers do not add or subtract rule constants by
hand; they wrap a mutation in `tracked()`, which measures the contribution
before and after and moves the author's karma by the difference:

    with karma.tracked(db, answer):
        answer.upvotes_count += 1

Deleting, hiding, or unpublishing drops the contribution to zero, so the same
two lines that award karma on an upvote also take it all back on a delete. One
rule, applied in one direction, with no separate revoke path to forget.

`compute_karma()` sums the same `contribution()` over everything a user owns,
so the incremental path and the reconciler cannot disagree about the rules --
they are reading the same function. See `scripts/refresh_karmas.py`.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Union

from sqlalchemy.orm import Session

from chafan_core.app import models, rules
from chafan_core.app.model_utils import is_live_answer, is_live_article

logger = logging.getLogger(__name__)

# Anything that earns its author karma, plus the User themselves (whose profile
# earns karma directly).
Earner = Union[
    models.Answer,
    models.Question,
    models.Article,
    models.Submission,
    models.Comment,
    models.User,
]


PROFILE_FIELDS = (
    "full_name",
    "github_username",
    "twitter_username",
    "linkedin_url",
    "homepage_url",
    "zhihu_url",
    "avatar_url",
    "gif_avatar_url",
    "personal_introduction",
)


def _profile_karma(user: models.User) -> int:
    karma = sum(rules.PROFILE_FIELD for field in PROFILE_FIELDS if getattr(user, field))
    for experiences in (user.work_experiences, user.education_experiences):
        karma += (
            min(len(experiences or []), rules.EXPERIENCE_MAX_ITEMS)
            * rules.EXPERIENCE_PER_ITEM
        )
    return karma


def contribution(item: Earner) -> int:
    """How much karma `item` earns its author in its current state.

    Zero once the item is deleted, hidden, or still an unpublished draft.
    """
    if isinstance(item, models.Answer):
        if not is_live_answer(item):
            return 0
        return rules.ANSWER_CREATE + item.upvotes_count * rules.ANSWER_UPVOTE
    if isinstance(item, models.Question):
        if item.is_hidden:
            return 0
        return rules.QUESTION_CREATE + item.upvotes_count * rules.QUESTION_UPVOTE
    if isinstance(item, models.Article):
        if not is_live_article(item):
            return 0
        return rules.ARTICLE_CREATE + item.upvotes_count * rules.ARTICLE_UPVOTE
    if isinstance(item, models.Submission):
        if item.is_hidden:
            return 0
        return rules.SUBMISSION_CREATE + item.upvotes_count * rules.SUBMISSION_UPVOTE
    if isinstance(item, models.Comment):
        if item.is_deleted:
            return 0
        return rules.COMMENT_CREATE
    if isinstance(item, models.User):
        return _profile_karma(item)
    raise TypeError(f"{type(item).__name__} does not earn karma")


def _earner(item: Earner) -> models.User:
    return item if isinstance(item, models.User) else item.author


def _move(db: Session, user: models.User, delta: int, reason: str) -> None:
    if delta == 0:
        return
    user.karma = (user.karma or 0) + delta
    db.add(user)
    logger.info(f"karma user_id={user.id} delta={delta:+d} reason={reason}")


@contextmanager
def tracked(db: Session, item: Earner) -> Iterator[None]:
    """Re-apply `item`'s karma to its author around a change to `item`.

    Wrap any mutation that can change what `item` is worth: an upvote, a
    cancelled upvote, publishing a draft, deleting, hiding, or editing a
    profile.
    """
    user = _earner(item)
    before = contribution(item)
    yield
    _move(db, user, contribution(item) - before, type(item).__name__.lower())


def record_new(db: Session, item: Earner) -> None:
    """Award karma for a just-created `item`. Nothing if it is still a draft."""
    _move(db, _earner(item), contribution(item), f"new_{type(item).__name__.lower()}")


def set_karma(db: Session, user: models.User, value: int) -> None:
    """Overwrite a user's karma. Only the reconciler should call this."""
    user.karma = value
    db.add(user)


def compute_karma(db: Session, user: models.User) -> int:
    """Recompute a user's karma from scratch, from everything they own.

    The authoritative answer, and the one `scripts/refresh_karmas.py` writes back.
    Uses the same `contribution()` as the incremental path, so the two can only
    disagree if an incremental hook is missing -- which is exactly what the
    reconciler exists to find.
    """
    owned: list[Earner] = [
        *user.answers,
        *user.questions,
        *user.articles,
        *user.submissions,
        *user.comments,
    ]
    return _profile_karma(user) + sum(contribution(item) for item in owned)
