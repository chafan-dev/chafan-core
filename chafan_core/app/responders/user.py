"""User ORM → full User API schema."""

from __future__ import annotations

from chafan_core.app import models, schemas
from chafan_core.app.config import settings
from chafan_core.app.schemas.security import IntlPhoneNumber


def user_schema_from_orm(user: models.User) -> schemas.User:
    base = schemas.UserInDBBase.from_orm(user)
    d = base.dict()
    if user.flags:
        d["flag_list"] = user.flags.split()
    else:
        d["flag_list"] = []

    enough_coins = user.remaining_coins >= settings.CREATE_SITE_COIN_DEDUCTION
    if settings.CREATE_SITE_FORCE_NEED_APPROVAL:
        d["can_create_public_site"] = False
        d["can_create_private_site"] = False
    else:
        d["can_create_public_site"] = (
            user.karma >= settings.MIN_KARMA_CREATE_PUBLIC_SITE and enough_coins
        )
        d["can_create_private_site"] = (
            user.karma >= settings.MIN_KARMA_CREATE_PRIVATE_SITE and enough_coins
        )
    if user.is_superuser:
        d["can_create_public_site"] = True
        d["can_create_private_site"] = True
    if user.phone_number_country_code and user.phone_number_subscriber_number:
        d["phone_number"] = IntlPhoneNumber(
            country_code=user.phone_number_country_code,
            subscriber_number=user.phone_number_subscriber_number,
        )
    return schemas.User(**d)
