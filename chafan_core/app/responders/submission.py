from typing import Any, Dict, Mapping, Optional, Tuple, Union
import logging
logger = logging.getLogger(__name__)

from chafan_core.app import crud, models, schemas
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import (
    filter_not_none,
)

from chafan_core.app import view_counters

def submission_schema_from_orm(
    cached_layer,
    submission: models.Submission,
) -> Optional[schemas.Submission]:
    if submission.is_hidden:
        return None
    base = schemas.SubmissionInDB.from_orm(submission)
    d = base.dict()
    d["site"] = cached_layer.materializer.site_schema_from_orm(submission.site)
    d["comments"] = filter_not_none(
        [cached_layer.materializer.comment_schema_from_orm(c) for c in submission.comments]
    )
    d["author"] = cached_layer.preview_of_user(submission.author)
    d["contributors"] = [cached_layer.preview_of_user(u) for u in submission.contributors]
    d["view_times"] = view_counters.get_viewcount_submission(cached_layer.broker, submission.id)
    if submission.description is not None:
        d["desc"] = RichText(
            source=submission.description,
            rendered_text=submission.description_text,
            editor=submission.description_editor,
        )
    return schemas.Submission(**d)

