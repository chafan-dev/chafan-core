"""Submission domain service (list helpers)."""

from __future__ import annotations

from typing import List, Optional

from chafan_core.app import crud, models, schemas
from chafan_core.app.recs.ranking import rank_submissions
from chafan_core.utils.base import filter_not_none
import chafan_core.app.responders as responders


def submission_schema(ctx, submission: models.Submission):
    return responders.submission.submission_schema_from_orm(ctx, submission)


def recent_k_of_site(ctx, site: models.Site, k: int) -> List[schemas.Submission]:
    return filter_not_none(
        [submission_schema(ctx, s) for s in site.submissions]
    )[:k]


def submissions_for_user(
    ctx, current_user_id: Optional[int]
) -> List[schemas.Submission]:
    db = ctx.get_db()
    if current_user_id:
        current_user = crud.user.get(db, id=current_user_id)
        assert current_user is not None
        submissions: List[schemas.Submission] = []
        for profile in current_user.profiles:
            submissions.extend(recent_k_of_site(ctx, profile.site, k=20))
        if len(submissions) == 0:
            for site in crud.site.get_all_public_readable(db):
                submissions.extend(
                    filter_not_none(
                        [submission_schema(ctx, s) for s in site.submissions]
                    )[:5]
                )
        return rank_submissions(submissions)

    submissions = []
    for site in crud.site.get_all_public_readable(db):
        submissions.extend(
            filter_not_none(
                [submission_schema(ctx, s) for s in site.submissions]
            )[:10]
        )
    return rank_submissions(submissions)


def site_submissions_for_user(
    ctx,
    *,
    site: models.Site,
    user_id: Optional[int],
    skip: int,
    limit: int,
) -> List[schemas.Submission]:
    submissions = rank_submissions(
        filter_not_none(
            [submission_schema(ctx, submission) for submission in site.submissions]
        )
    )
    return submissions[skip : skip + limit]


def list_suggestions(ctx, *, uuid: str):
    from chafan_core.app.common import OperationType
    from chafan_core.app.responders import suggestions as suggestions_responder
    from chafan_core.app.user_permission import check_user_in_site
    from chafan_core.utils.base import HTTPException_

    submission = crud.submission.get_by_uuid(ctx.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    check_user_in_site(
        ctx.get_db(),
        site=submission.site,
        user_id=ctx.unwrapped_principal_id(),
        op_type=OperationType.ReadSite,
    )
    mat = ctx.principal_view
    return filter_not_none(
        [
            suggestions_responder.submission_suggestion_schema_from_orm(mat, s)
            for s in submission.submission_suggestions
        ]
    )
