import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends
from fastapi.param_functions import Query
from sqlalchemy.orm import Session
import chafan_core.app.responders as responders


import logging
logger = logging.getLogger(__name__)


from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.common import OperationType
from chafan_core.app.config import settings
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.app.schemas.application import ApplicationCreate
from chafan_core.app.schemas.channel import SiteCreationSubject
from chafan_core.app.schemas.event import (
    ApplyJoinSiteInternal,
    CreateSiteInternal,
    CreateSiteNeedApprovalInternal,
    EventInternal,
)
from chafan_core.app.services import sites as sites_service
from chafan_core.app.services import submissions as submissions_service
from chafan_core.app.user_permission import user_in_site

from chafan_core.utils.base import EntityType, HTTPException_, filter_not_none, unwrap
from chafan_core.utils.constants import MAX_SITE_QUESTIONS_PAGINATION_LIMIT

router = APIRouter()


@router.post("/", response_model=schemas.CreateSiteResponse)
def create_site(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    site_in: schemas.SiteCreate,
) -> Any:
    """
    Create new site as user.
    """
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
            application_channel=ctx.channel_schema_from_orm(channel)
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
    new_site = sites_service.create_site(
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
    sites_service.create_site_profile(
        db,
        ctx.materializer,
        owner=new_site.moderator,
        site_uuid=new_site.uuid,
    )
    return schemas.CreateSiteResponse(
        created_site=sites_service.site_schema(ctx, new_site)
    )


@router.put("/{uuid}/config", response_model=schemas.Site, include_in_schema=False)
def config_site(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
    site_in: schemas.SiteUpdate,
) -> Any:
    """
    Configure a site as moderator.
    """
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
    new_site = sites_service.update_site(db, old_site=site, update_dict=site_in_dict)
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
    return sites_service.site_schema(ctx, new_site)


from chafan_core.app.common import OperationType

@router.get("/{subdomain}", response_model=schemas.Site)
def get_site_info(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
    subdomain: str
) -> Any:
    """
    Get a site's basic info.
    """
    logger.info(f"user {current_user_id} requesting site {subdomain}")
    #site_data = ctx.get_site_info(subdomain=subdomain)
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
    site_data = sites_service.site_schema(ctx, site)
    return site_data


@router.get("/{uuid}/questions/", response_model=List[schemas.QuestionPreview])
def get_site_questions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        le=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        gt=0,
    ),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    """
    Get a site's questions.
    """
    db = ctx.get_db()
    site = get_site(db, uuid)
    if not site.public_readable:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    max_questions = settings.API_LIMIT_SITES_GET_QUESTIONS_LIMIT
    limit = min(limit, max_questions)
    questions = crud.site.get_multi_questions(
        db, db_obj=site, skip=skip, limit=limit
    )
    return filter_not_none(
        [ctx.materializer.preview_of_question(q) for q in questions]
    )


@router.get(
    "/{uuid}/submissions/",
    response_model=List[schemas.Submission],
)
def get_site_submissions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    db: Session = Depends(deps.get_db),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        le=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        gt=0,
    ),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    """
    Get a site's submissions.
    """
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


@router.get("/{uuid}/apply", response_model=schemas.SiteApplicationResponse)
def get_site_apply(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Check application to site membership.
    """
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


@router.post("/{uuid}/apply", response_model=schemas.SiteApplicationResponse)
def site_apply(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    db: Session = Depends(deps.get_db),
    uuid: str,
) -> Any:
    """
    Apply to site membership.
    """
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
            sites_service.create_site_profile(
                db,
                ctx.materializer,
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


@router.delete("/{uuid}/membership", response_model=schemas.GenericResponse)
def remove_my_site_membership(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    db: Session = Depends(deps.get_db),
    uuid: str,
) -> Any:
    site = get_site(db, uuid)
    application = (
        db.query(models.Application)
        .filter_by(applicant_id=ctx.principal_id, applied_site_id=site.id)
        .first()
    )
    if application is not None:
        application.pending = False
    sites_service.remove_site_profile(
        db,
        owner_id=ctx.unwrapped_principal_id(),
        site_id=site.id,
    )
    db.commit()
    return schemas.GenericResponse()


@router.get("/{uuid}/webhooks/", response_model=List[schemas.Webhook])
def get_webhooks(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    site = get_site(ctx.get_db(), uuid)
    if site.moderator_id != ctx.principal_id:
        raise HTTPException_(
            status_code=500,
            detail="Unauthorized.",
        )
    return [
        ctx.materializer.webhook_schema_from_orm(webhook)
        for webhook in site.webhooks
    ]


@router.get("/{uuid}/related/", response_model=List[schemas.Site])
def get_related(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    site = get_site(ctx.get_db(), uuid)
    related_sites: Dict[int, models.Site] = {}
    if site.category_topic is not None:
        for s in crud.site.get_all_with_category_topic_ids(
            ctx.get_db(), site.category_topic.id
        ):
            related_sites[s.id] = s

    for site_id in sites_service.related_site_ids(
        ctx.get_db(), site.id, top_k=5
    ):
        if site_id not in related_sites:
            related_sites[site_id] = unwrap(
                crud.site.get(ctx.get_db(), site_id)
            )

    return [
        sites_service.site_schema(ctx, s)
        for s in related_sites.values()
    ]
