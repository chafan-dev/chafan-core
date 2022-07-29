import datetime
import math
from typing import List, Optional, Union

from chafan_core.app import models, schemas


def get_user_score(u: schemas.UserPreview) -> float:
    score = u.karma
    if u.social_annotations.follow_follows:
        score += u.social_annotations.follow_follows * 20
    return score


def get_user_model_score(u: models.User) -> float:
    score = u.karma + u.followers.count() * 5  # type: ignore
    return score


def rank_user_previews(users: List[schemas.UserPreview]) -> List[schemas.UserPreview]:
    return sorted(users, key=get_user_score, reverse=True)


def rank_users(users: List[models.User]) -> List[models.User]:
    return sorted(users, key=get_user_model_score, reverse=True)


# Return a freshness score between 0 and 1
def freshness(
    utc_now: datetime.datetime, updated_at: datetime.datetime, recency_boost: float
) -> float:
    return math.pow(1 / ((utc_now - updated_at).days + 1), recency_boost) / 2.0 + 0.5


def rank_submissions(
    submissions: Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]]
) -> Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]]:
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)

    def hotness(
        submission: Union[schemas.Submission, schemas.SubmissionForVisitor]
    ) -> float:
        return float(submission.upvotes_count + 1) * freshness(
            utc_now, submission.updated_at, recency_boost=1
        )

    return sorted(submissions, key=hotness, reverse=True)


def rank_answers(
    answers: List[models.Answer], principal_id: Optional[int]
) -> List[models.Answer]:
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)

    def compute_weight(answer: models.Answer) -> float:
        author_weight = 1000 if answer.author_id == principal_id else 1
        freshness_weight = freshness(utc_now, answer.updated_at, recency_boost=2)
        featured_weight = 2.0 if answer.featured_at else 1.0
        return (
            float(answer.upvotes_count + 1)
            * author_weight
            * freshness_weight
            * featured_weight
        )

    return sorted(answers, key=compute_weight, reverse=True)


def rank_site_profiles(site_profiles: List[models.Profile]) -> List[models.Profile]:
    return sorted(site_profiles, key=lambda p: p.karma, reverse=True)
