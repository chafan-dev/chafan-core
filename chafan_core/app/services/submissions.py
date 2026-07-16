"""Submission domain service (list helpers)."""

from __future__ import annotations

from typing import List, Optional

from chafan_core.app import crud, models, schemas
from chafan_core.app.recs.ranking import rank_submissions
from chafan_core.utils.base import filter_not_none


def recent_k_of_site(cached_layer, site: models.Site, k: int) -> List[schemas.Submission]:
    return filter_not_none(
        [cached_layer.materializer.submission_schema_from_orm(s) for s in site.submissions]
    )[:k]


def submissions_for_user(
    cached_layer, current_user_id: Optional[int]
) -> List[schemas.Submission]:
    db = cached_layer.get_db()
    if current_user_id:
        current_user = crud.user.get(db, id=current_user_id)
        assert current_user is not None
        submissions: List[schemas.Submission] = []
        for profile in current_user.profiles:
            submissions.extend(recent_k_of_site(cached_layer, profile.site, k=20))
        if len(submissions) == 0:
            for site in crud.site.get_all_public_readable(db):
                submissions.extend(
                    filter_not_none(
                        [
                            cached_layer.materializer.submission_schema_from_orm(s)
                            for s in site.submissions
                        ]
                    )[:5]
                )
        return rank_submissions(submissions)

    submissions = []
    for site in crud.site.get_all_public_readable(db):
        submissions.extend(
            filter_not_none(
                [
                    cached_layer.materializer.submission_schema_from_orm(s)
                    for s in site.submissions
                ]
            )[:10]
        )
    return rank_submissions(submissions)


def site_submissions_for_user(
    cached_layer,
    *,
    site: models.Site,
    user_id: Optional[int],
    skip: int,
    limit: int,
) -> List[schemas.Submission]:
    submissions = rank_submissions(
        filter_not_none(
            [
                cached_layer.materializer.submission_schema_from_orm(submission)
                for submission in site.submissions
            ]
        )
    )
    return submissions[skip : skip + limit]
