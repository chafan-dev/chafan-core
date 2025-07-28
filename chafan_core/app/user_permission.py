import datetime
from typing import Any, Dict, Mapping, Optional, Tuple, Union
import logging
logger = logging.getLogger(__name__)

from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.config import settings
from chafan_core.app.data_broker import DataBroker


import logging
logger = logging.getLogger(__name__)

# TODO everything about user permission, including if they can create a site (KARMA), invite a user, write an answer, etc, should be moved into this file. 2025-07-08


def get_active_site_profile(
    db: Session, site: models.Site, user_id: int
) -> Optional[models.Profile]:
    return crud.profile.get_by_user_and_site(db, owner_id=user_id, site_id=site.id)

def user_in_site(
    db: Session,
    site: models.Site,
    user_id: int,
    op_type: OperationType,
) -> bool:
    if op_type == OperationType.ReadSite and site.public_readable:
        return True
    if op_type == OperationType.WriteSiteAnswer and site.public_writable_answer:
        return True
    if op_type == OperationType.WriteSiteSubmission and site.public_writable_submission:
        return True
    if op_type == OperationType.WriteSiteQuestion and site.public_writable_question:
        return True
    if op_type == OperationType.WriteSiteComment and site.public_writable_comment:
        return True
    if get_active_site_profile(db, site=site, user_id=user_id) is None:
        return False
    if op_type == OperationType.AddSiteMember and not site.addable_member:
        return False
    return True

