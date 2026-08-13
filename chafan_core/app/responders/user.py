"""User ORM → full User API schema."""

from __future__ import annotations

from chafan_core.app import models, rules, schemas
from chafan_core.app.config import settings
from chafan_core.app.schemas.security import IntlPhoneNumber
from chafan_core.utils.constants import (
    unknown_user_full_name,
    unknown_user_handle,
    unknown_user_uuid,
)
from chafan_core.utils.validators import StrippedNonEmptyBasicStr

_ANONYMOUS_USER_PREVIEW = schemas.UserPreview(
    uuid=unknown_user_uuid,
    handle=StrippedNonEmptyBasicStr(unknown_user_handle),
    full_name=unknown_user_full_name,
)


def plain_preview_of_user(user: models.User) -> schemas.UserPreview:
    """User preview without principal-relative social annotations."""
    if not user.is_active:
        return _ANONYMOUS_USER_PREVIEW
    return schemas.UserPreview(
        uuid=user.uuid,
        karma=user.karma,
        full_name=user.full_name,
        handle=user.handle,
        avatar_url=user.avatar_url,
        personal_introduction=user.personal_introduction,
    )


def user_schema_from_orm(user: models.User) -> schemas.User:
    base = schemas.UserInDBBase.from_orm(user)
    d = base.dict()
    if user.flags:
        d["flag_list"] = user.flags.split()
    else:
        d["flag_list"] = []

    d["can_create_public_site"] = (
        user.karma >= rules.MIN_KARMA_CREATE_SITE
        and user.remaining_coins >= rules.CREATE_SITE_COST
    )
    # Private sites are sunset: `services.sites.create_site_for_user` refuses a
    # non-public site from anyone but a superuser, so no karma threshold can
    # unlock this. The field stays in the API contract, reporting the truth.
    d["can_create_private_site"] = False
    if user.is_superuser:
        d["can_create_public_site"] = True
        d["can_create_private_site"] = True
    if user.phone_number_country_code and user.phone_number_subscriber_number:
        d["phone_number"] = IntlPhoneNumber(
            country_code=user.phone_number_country_code,
            subscriber_number=user.phone_number_subscriber_number,
        )
    return schemas.User(**d)
