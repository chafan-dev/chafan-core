"""Site domain service."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.config import settings
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.recs.matrices import similar_entity_ids
from chafan_core.app.recs.ranking import rank_site_profiles
from chafan_core.app.schemas.application import ApplicationCreate
from chafan_core.app.schemas.channel import SiteCreationSubject
from chafan_core.app.schemas.event import (
    ApplyJoinSiteInternal,
    CreateSiteInternal,
    CreateSiteNeedApprovalInternal,
    EventInternal,
)
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.app.user_permission import check_user_in_site, user_in_site
from chafan_core.utils.base import EntityType, HTTPException_, unwrap
import chafan_core.app.responders as responders

logger = logging.getLogger(__name__)


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


def get_site_maps(ctx) -> schemas.site.SiteMaps:
    """Build public site map (no redis content cache)."""
    db = ctx.get_db()
    sites = crud.site.get_all(db)
    site_maps: dict = {}
    sites_without_topics: List[schemas.Site] = []
    for s in sites:
        if not s.public_readable:
            continue
        site_data = site_schema(ctx, s)
        if s.category_topic is not None:
            pass  # category_topic deprecated
        sites_without_topics.append(site_data)
    return schemas.site.SiteMaps(
        site_maps=list(site_maps.values()),
        sites_without_topics=sites_without_topics,
    )


def get_site_by_subdomain(db: Session, subdomain: str) -> Optional[models.Site]:
    return crud.site.get_by_subdomain(db, subdomain=subdomain)


def site_schema(ctx, site: models.Site) -> schemas.Site:
    return responders.site.site_schema_from_orm(ctx, site)


def get_site_info(ctx, *, subdomain: str) -> Optional[schemas.Site]:
    site = get_site_by_subdomain(ctx.get_db(), subdomain)
    if site is None:
        return None
    return site_schema(ctx, site)


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
    mat = ctx.principal_view
    return filter_not_none([mat.preview_of_question(q) for q in questions])


def list_site_webhooks(ctx, *, site: models.Site) -> List[schemas.Webhook]:
    from chafan_core.app.responders import misc as misc_responder

    mat = ctx.principal_view
    return [misc_responder.webhook_schema_from_orm(mat, w) for w in site.webhooks]


def create_site_for_user(ctx, *, site_in: schemas.SiteCreate) -> schemas.CreateSiteResponse:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    needs_approval = settings.CREATE_SITE_FORCE_NEED_APPROVAL
    if current_user.remaining_coins < settings.CREATE_SITE_COIN_DEDUCTION:
        needs_approval = True
    if current_user.karma < settings.MIN_KARMA_CREATE_PUBLIC_SITE:
        needs_approval = True
    if current_user.is_superuser:
        needs_approval = False
    elif site_in.permission_type != "public":
        raise HTTPException_(
            status_code=400,
            detail="Not allowed to create a private site",
        )
    if needs_approval:
        raise HTTPException_(
            status_code=400,
            detail="Not allowed to create site with approval (yet)",
        )
    if needs_approval:
        from chafan_core.app.responders import misc as misc_responder

        admin = crud.user.get_superuser(db)
        channel = crud.channel.get_or_create_private_channel_with(
            db,
            host_user=current_user,
            with_user=admin,
            obj_in=schemas.ChannelCreate(
                private_with_user_uuid=admin.uuid,
                subject=SiteCreationSubject(site_in=site_in),
            ),
        )
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        crud.notification.create_with_content(
            ctx.broker,
            receiver_id=admin.id,
            event=EventInternal(
                created_at=utc_now,
                content=CreateSiteNeedApprovalInternal(
                    subject_id=current_user.id,
                    channel_id=channel.id,
                ),
            ),
        )
        return schemas.CreateSiteResponse(
            application_channel=misc_responder.channel_schema_from_orm(
                ctx.principal_view, channel
            )
        )
    site = crud.site.get_by_subdomain(db, subdomain=site_in.subdomain)
    if site:
        raise HTTPException_(
            status_code=400,
            detail="The site with this subdomain already exists in the system.",
        )
    if site_in.name:
        site = crud.site.get_by_name(db, name=site_in.name)
        if site:
            raise HTTPException_(
                status_code=400,
                detail="The site with this name already exists in the system.",
            )
    category_topic_id: Optional[int] = None
    if site_in.category_topic_uuid:
        raise HTTPException_(
            status_code=400,
            detail="Attach a category topic id when creating a site is disabled.",
        )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    super_user = crud.user.get_superuser(db)
    new_site = create_site(
        db,
        site_in=site_in,
        moderator=current_user,
        category_topic_id=category_topic_id,
    )
    crud.coin_payment.make_payment(
        db,
        obj_in=schemas.CoinPaymentCreate(
            payee_id=super_user.id,
            amount=settings.CREATE_SITE_COIN_DEDUCTION,
            event_json=EventInternal(
                created_at=utc_now,
                content=CreateSiteInternal(
                    subject_id=current_user.id,
                    site_id=new_site.id,
                ),
            ).json(),
        ),
        payer=current_user,
        payee=super_user,
    )
    create_site_profile(
        db,
        ctx.principal_view,
        owner=new_site.moderator,
        site_uuid=new_site.uuid,
    )
    return schemas.CreateSiteResponse(
        created_site=site_schema(ctx, new_site)
    )


def config_site(
    ctx, *, uuid: str, site_in: schemas.SiteUpdate
) -> schemas.Site:
    db = ctx.get_db()
    site = crud.site.get_by_uuid(db, uuid=uuid)
    if not site:
        raise HTTPException_(
            status_code=404,
            detail="The site with this id does not exist in the system",
        )
    if ctx.principal_id != site.moderator_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    site_in_dict = site_in.dict(exclude_unset=True)
    if site_in.moderator_uuid is not None:
        moderator = crud.user.get_by_uuid(db, uuid=site_in.moderator_uuid)
        if moderator is None:
            raise HTTPException_(
                status_code=400,
                detail="Invalid new moderator UUID",
            )
        del site_in_dict["moderator_uuid"]
        site_in_dict["moderator_id"] = moderator.id
    if site_in.category_topic_uuid:
        category_topic = crud.topic.get_by_uuid(db, uuid=site_in.category_topic_uuid)
        if category_topic is None or not category_topic.is_category:
            raise HTTPException_(
                status_code=400,
                detail="Invalid category topic id.",
            )
        del site_in_dict["category_topic_uuid"]
        site_in_dict["category_topic_id"] = category_topic.id
    new_site = update_site(db, old_site=site, update_dict=site_in_dict)
    if site_in.topic_uuids is not None:
        new_topics = []
        for topic_uuid in site_in.topic_uuids:
            topic = crud.topic.get_by_uuid(db, uuid=topic_uuid)
            if topic is None:
                raise HTTPException_(
                    status_code=400,
                    detail="The topic doesn't exist.",
                )
            new_topics.append(topic)
        new_site.topics = new_topics
        db.add(new_site)
        db.commit()
    return site_schema(ctx, new_site)


def get_site_info_for_user(
    ctx, *, subdomain: str, current_user_id: Optional[int]
) -> schemas.Site:
    logger.info(f"user {current_user_id} requesting site {subdomain}")
    db = ctx.get_db()
    site = crud.site.get_by_subdomain(db, subdomain=subdomain)

    if not site:
        raise HTTPException_(
            status_code=404,
            detail="The site with this id does not exist in the system",
        )
    if not user_in_site(db, site, current_user_id, OperationType.ReadSite):
        logger.info("user has no permission")
        #TODO add audit
        raise HTTPException_(
            status_code=404,
            detail="The site with this id does not exist in the system",
        )
    return site_schema(ctx, site)


def list_site_questions(
    ctx, *, uuid: str, skip: int, limit: int
) -> List[schemas.QuestionPreview]:
    db = ctx.get_db()
    site = get_site(db, uuid)
    if not site.public_readable:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    max_questions = settings.API_LIMIT_SITES_GET_QUESTIONS_LIMIT
    limit = min(limit, max_questions)
    return list_site_question_previews(ctx, site=site, skip=skip, limit=limit)


def list_site_submissions(
    ctx, *, uuid: str, skip: int, limit: int, current_user_id: Optional[int]
) -> List[schemas.Submission]:
    from chafan_core.app.services import submissions as submissions_service

    db = ctx.get_db()
    site = get_site(db, uuid)
    if current_user_id:
        check_user_in_site(
            db, site=site, user_id=current_user_id, op_type=OperationType.ReadSite
        )
    else:
        if not site.public_readable:
            raise HTTPException_(
                status_code=400,
                detail="Unauthorized.",
            )
    return submissions_service.site_submissions_for_user(
        ctx, site=site, user_id=current_user_id, skip=skip, limit=limit
    )


def get_site_apply(db: Session, *, uuid: str, current_user_id: int) -> schemas.SiteApplicationResponse:
    site = get_site(db, uuid)
    if not site:
        raise HTTPException_(
            status_code=400,
            detail="The site doesn't exist.",
        )
    application = (
        db.query(models.Application)
        .filter_by(applicant_id=current_user_id, applied_site_id=site.id)
        .first()
    )
    if application is not None:
        return schemas.SiteApplicationResponse(applied_before=True)
    return schemas.SiteApplicationResponse(applied_before=False)


def site_apply(ctx, *, uuid: str) -> schemas.SiteApplicationResponse:
    db = ctx.get_db()
    site = get_site(db, uuid)
    current_user = ctx.get_current_active_user()
    application = (
        db.query(models.Application)
        .filter_by(applicant_id=current_user.id, applied_site_id=site.id)
        .first()
    )
    if application is not None:
        raise HTTPException_(
            status_code=400,
            detail="Applied.",
        )
    if site.min_karma_for_application is not None:
        if current_user.karma < site.min_karma_for_application:
            raise HTTPException_(
                status_code=400,
                detail="Insufficient karma for joining site.",
            )
    if site.email_domain_suffix_for_application is not None:
        raise HTTPException_(
            status_code=400,
            detail="Email Verify Turned off.",
        )
    if site.auto_approval or current_user.is_superuser:
        existing_profile = crud.profile.get_by_user_and_site(
            db, owner_id=current_user.id, site_id=site.id
        )
        if not existing_profile:
            create_site_profile(
                db,
                ctx.principal_view,
                owner=current_user,
                site_uuid=site.uuid,
            )
        return schemas.SiteApplicationResponse(auto_approved=True)
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    crud.notification.create_with_content(
        ctx,
        receiver_id=site.moderator_id,
        event=EventInternal(
            created_at=utc_now,
            content=ApplyJoinSiteInternal(
                subject_id=current_user.id,
                site_id=site.id,
            ),
        ),
    )
    # FIXME 圈子管理功能还是不可用的，不确定问题在前端还是后端 2025-Jul-27
    crud.application.create_with_applicant(
        db,
        create_in=ApplicationCreate(applied_site_id=site.id),
        applicant_id=current_user.id,
    )
    return schemas.SiteApplicationResponse()


def remove_my_site_membership(ctx, *, uuid: str) -> None:
    db = ctx.get_db()
    site = get_site(db, uuid)
    application = (
        db.query(models.Application)
        .filter_by(applicant_id=ctx.principal_id, applied_site_id=site.id)
        .first()
    )
    if application is not None:
        application.pending = False
    remove_site_profile(
        db,
        owner_id=ctx.unwrapped_principal_id(),
        site_id=site.id,
    )
    db.commit()


def get_webhooks(ctx, *, uuid: str) -> List[schemas.Webhook]:
    site = get_site(ctx.get_db(), uuid)
    if site.moderator_id != ctx.principal_id:
        raise HTTPException_(
            status_code=500,
            detail="Unauthorized.",
        )
    return list_site_webhooks(ctx, site=site)


def get_related_sites(ctx, *, uuid: str) -> List[schemas.Site]:
    site = get_site(ctx.get_db(), uuid)
    related_sites: Dict[int, models.Site] = {}
    if site.category_topic is not None:
        for s in crud.site.get_all_with_category_topic_ids(
            ctx.get_db(), site.category_topic.id
        ):
            related_sites[s.id] = s

    for site_id in related_site_ids(ctx.get_db(), site.id, top_k=5):
        if site_id not in related_sites:
            related_sites[site_id] = unwrap(crud.site.get(ctx.get_db(), site_id))

    return [site_schema(ctx, s) for s in related_sites.values()]
