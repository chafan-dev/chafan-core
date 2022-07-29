import random
from typing import List

from sqlalchemy.orm.session import Session

from chafan_core.app import crud, models
from chafan_core.app.materialize import get_active_site_profile
from chafan_core.app.recs.ranking import rank_users

_MAX_SITE_INTERESTING_QUESTION_SIZE = 20


def compute_site_interesting_question_ids(site: models.Site) -> List[int]:
    """Baseline impl: randomly select batches * batch_size candidates"""
    qs = [q.id for q in site.questions if not q.is_hidden]
    if len(qs) > _MAX_SITE_INTERESTING_QUESTION_SIZE:
        qs = random.sample(qs, k=_MAX_SITE_INTERESTING_QUESTION_SIZE)
    return qs


_MAX_INTERESTING_QUESTION_PER_USER = 50


def compute_interesting_questions_ids_for_normal_user(
    db: Session,
    current_user: models.User,
) -> List[int]:
    questions: List[int] = []
    for site in db.query(models.Site):
        if site.public_readable or get_active_site_profile(
            db, site=site, user_id=current_user.id
        ):
            questions.extend(compute_site_interesting_question_ids(site))
    if len(questions) <= _MAX_INTERESTING_QUESTION_PER_USER:
        return questions
    else:
        return random.sample(questions, _MAX_INTERESTING_QUESTION_PER_USER)


def compute_interesting_questions_ids_for_visitor_user(
    db: Session,
) -> List[int]:
    questions_for_visitors: List[int] = []
    for site in crud.site.get_all_public_readable(db):
        questions_for_visitors.extend(compute_site_interesting_question_ids(site))
    return questions_for_visitors


def compute_interesting_users_ids_for_visitor_user(
    db: Session,
) -> List[int]:
    return [u.id for u in rank_users(crud.user.get_all_active_users(db))[:50]]


def compute_interesting_users_ids_for_normal_user(
    db: Session,
    current_user: models.User,
) -> List[int]:
    user_candidates = [
        u
        for u in crud.user.get_all_active_users(db)
        if u not in current_user.followed and u != current_user
    ]
    return [u.id for u in rank_users(user_candidates)[:50]]
