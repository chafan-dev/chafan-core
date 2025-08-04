from typing import Any, Mapping
from chafan_core.app import models, schemas

import logging
logger = logging.getLogger(__name__)

_VISIBLE_QUESTION_CONDITIONS = {
    "is_hidden": False,
}
_VISIBLE_SUBMISSION_CONDITIONS = {
    "is_hidden": False,
}

def keep_items(questions: Any, conditions: Mapping[str, Any]) -> Any:
    return questions.filter_by(**conditions)

def site_schema_from_orm(cached_layer, site: models.Site) -> schemas.Site:
    base = schemas.SiteInDBBase.from_orm(site)
    site_dict = base.dict()
    site_dict["moderator"] = cached_layer.preview_of_user(site.moderator)
    site_dict["questions_count"] = keep_items(
        site.questions, _VISIBLE_QUESTION_CONDITIONS
    ).count()
    site_dict["submissions_count"] = keep_items(
        site.submissions, _VISIBLE_SUBMISSION_CONDITIONS
    ).count()
    site_dict["members_count"] = len(site.profiles)
    site_dict["category_topic"] = None
    return schemas.Site(**site_dict)
