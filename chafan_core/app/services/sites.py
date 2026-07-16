"""Site domain service."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.materialize import Materializer
from chafan_core.app.recs.matrices import similar_entity_ids
from chafan_core.app.recs.ranking import rank_site_profiles
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.utils.base import EntityType


def create_site(
    db: Session,
    *,
    site_in: SiteCreate,
    moderator: models.User,
    category_topic_id: Optional[int],
) -> models.Site:
    return crud.site.create_with_permission_type(
        db,
        obj_in=site_in,
        moderator=moderator,
        category_topic_id=category_topic_id,
    )


def create_site_profile(
    db: Session,
    materializer: Materializer,
    *,
    owner: models.User,
    site_uuid: str,
) -> schemas.Profile:
    data = crud.profile.create_with_owner(
        db,
        obj_in=schemas.ProfileCreate(
            owner_uuid=owner.uuid,
            site_uuid=site_uuid,
        ),
    )
    return materializer.profile_schema_from_orm(data)


def remove_site_profile(db: Session, *, owner_id: int, site_id: int) -> None:
    crud.profile.remove_by_user_and_site(db, owner_id=owner_id, site_id=site_id)


def related_site_ids(db: Session, site_id: int, top_k: int = 10) -> List[int]:
    return similar_entity_ids(
        db, entity_id=site_id, entity_type=EntityType.sites, top_k=top_k
    )


def site_profiles_for_user(
    db: Session, materializer: Materializer, user_id: int
) -> List[schemas.Profile]:
    current_user = crud.user.get(db, id=user_id)
    assert current_user is not None
    return [
        materializer.profile_schema_from_orm(p)
        for p in rank_site_profiles(current_user.profiles)
    ]
