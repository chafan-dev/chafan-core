"""Similarity / fanout / contribution matrices (formerly CachedLayer recs)."""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.utils.base import EntityType

# Entity.id -> ranked similar entity ids
MatrixType = Dict[int, List[int]]
# User.id -> { User.uuid -> count }
WeightedMatrixType = Dict[int, Dict[str, int]]
# List of (year, day_contribs[1..364])
UserContributions = List[Tuple[int, List[int]]]


def compute_entity_similarity_matrix(db: Session, entity_type: EntityType) -> MatrixType:
    entities: List[Tuple[int, Set[str]]] = []
    if entity_type == EntityType.sites:
        for site in crud.site.get_all(db):
            if site.keywords:
                entities.append((site.id, set(site.keywords)))
    elif entity_type == EntityType.users:
        for user in crud.user.get_all_active_users(db):
            if user.keywords:
                entities.append((user.id, set(user.keywords)))
    else:
        raise Exception(f"Unknown entity type: {entity_type}")

    matrix: MatrixType = {}
    for query_id, query_keywords in entities:
        candidates = []
        for candidate_id, candidate_keywords in entities:
            if candidate_id == query_id:
                continue
            candidates.append(
                (candidate_id, len(candidate_keywords.intersection(query_keywords)))
            )
        candidates.sort(key=lambda p: p[1], reverse=True)
        matrix[query_id] = [cid for cid, _ in candidates[:50]]
    return matrix


def compute_follow_follow_fanout(db: Session) -> WeightedMatrixType:
    matrix: WeightedMatrixType = {}
    for user in crud.user.get_all_active_users(db):
        user_ids: Counter = Counter()
        for followed in user.followed:
            for followed_followed in followed.followed:
                if followed_followed.id != user.id:
                    user_ids[followed_followed.uuid] += 1
        matrix[user.id] = dict(user_ids)
    return matrix


def compute_user_contributions(user: models.User) -> UserContributions:
    d: Dict[int, Dict[int, Dict[str, int]]] = {}

    def incr(timestamp: datetime.datetime, action: str) -> None:
        year = timestamp.year
        day = min(timestamp.timetuple().tm_yday, 364)
        if year not in d:
            d[year] = {}
        if day not in d[year]:
            d[year][day] = {}
        if action not in d[year][day]:
            d[year][day][action] = 0
        d[year][day][action] += 1

    for answer in user.answers:
        incr(answer.updated_at, "answer")
    for article in user.articles:
        incr(article.created_at, "article")
    for question in user.questions:
        incr(question.created_at, "question")
    for submission in user.submissions:
        incr(submission.created_at, "submission")

    ret: UserContributions = []
    if not d:
        return ret
    for year in reversed(range(min(d.keys()), max(d.keys()) + 1)):
        day_contribs = []
        for day in range(1, 365):
            if year not in d or day not in d[year]:
                day_contribs.append(0)
            else:
                v = 0
                if "answer" in d[year][day]:
                    v += max(d[year][day]["answer"], 2)
                if "question" in d[year][day]:
                    v += max(d[year][day]["question"], 1)
                if "submission" in d[year][day]:
                    v += max(int(float(d[year][day]["submission"]) / 2.0), 1)
                if "article" in d[year][day]:
                    v += max(d[year][day]["article"], 2)
                day_contribs.append(min(int(v), 3))
        ret.append((year, day_contribs))
    return ret


def similar_entity_ids(
    db: Session,
    *,
    entity_id: int,
    entity_type: EntityType,
    top_k: int = 10,
    matrix: Optional[MatrixType] = None,
) -> List[int]:
    m = matrix if matrix is not None else compute_entity_similarity_matrix(db, entity_type)
    if entity_id not in m:
        return []
    return m[entity_id][:top_k]
