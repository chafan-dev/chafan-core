"""Site domain service."""

from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.recs.matrices import similar_entity_ids
from chafan_core.app.recs.ranking import rank_site_profiles
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.utils.base import EntityType
import chafan_core.app.responders as responders


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
    mat: Any,
    *,
    owner: models.User,
    site_uuid: str,
) -> schemas.Profile:
    """mat: PrincipalView-like with site/user previews (or profile_schema_from_orm)."""
    from chafan_core.app.responders import misc as misc_responder

    data = crud.profile.create_with_owner(
        db,
        obj_in=schemas.ProfileCreate(
            owner_uuid=owner.uuid,
            site_uuid=site_uuid,
        ),
    )
    if hasattr(mat, "profile_schema_from_orm"):
        return mat.profile_schema_from_orm(data)
    return misc_responder.profile_schema_from_orm(mat, data)


def remove_site_profile(db: Session, *, owner_id: int, site_id: int) -> None:
    crud.profile.remove_by_user_and_site(db, owner_id=owner_id, site_id=site_id)


def related_site_ids(db: Session, site_id: int, top_k: int = 10) -> List[int]:
    return similar_entity_ids(
        db, entity_id=site_id, entity_type=EntityType.sites, top_k=top_k
    )


def site_profiles_for_user(
    db: Session, mat: Any, user_id: int
) -> List[schemas.Profile]:
    from chafan_core.app.responders import misc as misc_responder

    current_user = crud.user.get(db, id=user_id)
    assert current_user is not None
    profiles = rank_site_profiles(current_user.profiles)
    if hasattr(mat, "profile_schema_from_orm"):
        return [mat.profile_schema_from_orm(p) for p in profiles]
    return [misc_responder.profile_schema_from_orm(mat, p) for p in profiles]


def get_site_maps(cached_layer) -> schemas.site.SiteMaps:
    """Build public site map (no redis content cache)."""
    db = cached_layer.get_db()
    sites = crud.site.get_all(db)
    site_maps: dict = {}
    sites_without_topics: List[schemas.Site] = []
    for s in sites:
        if not s.public_readable:
            continue
        site_data = site_schema(cached_layer, s)
        if s.category_topic is not None:
            pass  # category_topic deprecated
        sites_without_topics.append(site_data)
    return schemas.site.SiteMaps(
        site_maps=list(site_maps.values()),
        sites_without_topics=sites_without_topics,
    )


def get_site_by_subdomain(db: Session, subdomain: str) -> Optional[models.Site]:
    return crud.site.get_by_subdomain(db, subdomain=subdomain)


def site_schema(cached_layer, site: models.Site) -> schemas.Site:
    return responders.site.site_schema_from_orm(cached_layer, site)


def get_site_info(cached_layer, *, subdomain: str) -> Optional[schemas.Site]:
    site = get_site_by_subdomain(cached_layer.get_db(), subdomain)
    if site is None:
        return None
    return site_schema(cached_layer, site)


def update_site(
    db: Session, *, old_site: models.Site, update_dict: dict
) -> models.Site:
    return crud.site.update(db, db_obj=old_site, obj_in=update_dict)


def list_site_question_previews(
    ctx, *, site: models.Site, skip: int, limit: int
) -> List[schemas.QuestionPreview]:
    from chafan_core.utils.base import filter_not_none

    questions = crud.site.get_multi_questions(
        ctx.get_db(), db_obj=site, skip=skip, limit=limit
    )
    mat = ctx.materializer
    return filter_not_none([mat.preview_of_question(q) for q in questions])


def list_site_webhooks(ctx, *, site: models.Site) -> List[schemas.Webhook]:
    from chafan_core.app.responders import misc as misc_responder

    mat = ctx.materializer
    return [misc_responder.webhook_schema_from_orm(mat, w) for w in site.webhooks]
