from typing import Optional
import logging

import chafan_core.app.responders as responders
from chafan_core.app import models, schemas, user_permission, view_counters
from chafan_core.app.common import OperationType
from chafan_core.app.responders._util import get_db, shaper
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import filter_not_none

logger = logging.getLogger(__name__)


def submission_schema_from_orm(
    ctx,
    submission: models.Submission,
) -> Optional[schemas.Submission]:
    if submission.is_hidden:
        return None
    if not user_permission.user_in_site(
        get_db(ctx),
        site=submission.site,
        user_id=ctx.principal_id,
        op_type=OperationType.ReadSite,
    ):
        return None
    mat = shaper(ctx)
    base = schemas.SubmissionInDB.from_orm(submission)
    d = base.dict()
    d["site"] = responders.site.site_schema_from_orm(ctx, submission.site)
    d["comments"] = filter_not_none(
        [mat.comment_schema_from_orm(c) for c in submission.comments]
    )
    d["author"] = ctx.preview_of_user(submission.author)
    d["contributors"] = [
        ctx.preview_of_user(u) for u in submission.contributors
    ]
    d["view_times"] = view_counters.get_viewcount_submission(ctx, submission.id)
    if submission.description is not None:
        d["desc"] = RichText(
            source=submission.description,
            rendered_text=submission.description_text,
            editor=submission.description_editor,
        )
    return schemas.Submission(**d)

