from typing import Any, List, Optional, Union

from fastapi import APIRouter, Depends
from fastapi.param_functions import Query
from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, view_counters
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType
from chafan_core.app.materialize import user_in_site
from chafan_core.app.model_utils import is_live_answer, is_live_article
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.user import (
    UserEducationExperienceInternal,
    UserWorkExperienceInternal,
    YearContributions,
)
from chafan_core.utils.base import HTTPException_, filter_not_none, unwrap
from chafan_core.utils.constants import (
    MAX_USER_ANSWERS_PAGINATION_LIMIT,
    MAX_USER_ARTICLES_PAGINATION_LIMIT,
    MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
    MAX_USER_QUESTIONS_PAGINATION_LIMIT,
    MAX_USER_SUBMISSIONS_PAGINATION_LIMIT,
)
from chafan_core.utils.validators import StrippedNonEmptyBasicStr

router = APIRouter()


def _get_work_exps(db: Session, user: models.User) -> List[schemas.UserWorkExperience]:
    work_exps: List[UserWorkExperienceInternal] = []
    if user.work_experiences is not None:
        work_exps = parse_obj_as(
            List[UserWorkExperienceInternal], user.work_experiences
        )
    ret = []
    for work_exp in work_exps:
        company_topic = crud.topic.get_by_uuid(db, uuid=work_exp.company_topic_uuid)
        position_topic = crud.topic.get_by_uuid(db, uuid=work_exp.position_topic_uuid)
        ret.append(
            schemas.UserWorkExperience(
                company_topic=schemas.Topic.from_orm(company_topic),
                position_topic=schemas.Topic.from_orm(position_topic),
            )
        )
    return ret


def _get_edu_exps(
    db: Session, user: models.User
) -> List[schemas.UserEducationExperience]:
    edu_exps: List[UserEducationExperienceInternal] = []
    if user.education_experiences is not None:
        edu_exps = parse_obj_as(
            List[UserEducationExperienceInternal], user.education_experiences
        )
    ret = []
    for edu_exp in edu_exps:
        school_topic = crud.topic.get_by_uuid(db, uuid=edu_exp.school_topic_uuid)
        ret.append(
            schemas.UserEducationExperience(
                school_topic=schemas.Topic.from_orm(school_topic),
                level=edu_exp.level_name,
                major=edu_exp.major,
                enroll_year=edu_exp.enroll_year,
                graduate_year=edu_exp.graduate_year,
            )
        )
    return ret


def _get_user_public_visitor(
    cached_layer: CachedLayer, user: models.User, view_times: int
) -> schemas.UserPublicForVisitor:
    preview = cached_layer.preview_of_user(user)
    return schemas.UserPublicForVisitor(
        **preview.dict(),
        gif_avatar_url=user.gif_avatar_url,
        answers_count=len(
            [answer for answer in user.answers if is_live_answer(answer)]
        ),
        submissions_count=len(
            [submission for submission in user.submissions if not submission.is_hidden]
        ),
        questions_count=len(
            [question for question in user.questions if not question.is_hidden]
        ),
        articles_count=len(
            [article for article in user.articles if is_live_article(article)]
        ),
        created_at=user.created_at,
        profile_view_times=view_times,
    )


@router.get(
    "/{handle}", response_model=Union[schemas.UserPublic, schemas.UserPublicForVisitor]  # type: ignore
)
def get_user_public(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    handle: StrippedNonEmptyBasicStr,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    db = cached_layer.get_db()
    user = crud.user.get_by_handle(db, handle=handle)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    view_times = view_counters.get_views(user.uuid, "profile")
    if current_user_id is None:
        return _get_user_public_visitor(cached_layer, user, view_times)
    selected_profiles = [
        cached_layer.materializer.profile_schema_from_orm(profile)
        for profile in user.profiles
        if user_in_site(
            db,
            site=profile.site,
            user_id=current_user_id,
            op_type=OperationType.ReadSite,
        )
    ]
    view_counters.add_view(user.uuid, "profile", current_user_id)
    db.commit()
    about_content = None
    if user.about is not None:
        about_content = RichText(source=user.about, editor="wysiwyg")
    u = _get_user_public_visitor(cached_layer, user, view_times)
    contributions = [
        YearContributions(year=year, data=data)
        for year, data in cached_layer.get_user_contributions(user)
    ]
    return schemas.UserPublic(
        **u.dict(),
        about_content=about_content,
        profiles=selected_profiles,
        residency_topics=[schemas.Topic.from_orm(t) for t in user.residency_topics],
        profession_topics=[schemas.Topic.from_orm(t) for t in user.profession_topics],
        github_username=user.github_username,
        twitter_username=user.twitter_username,
        linkedin_url=user.linkedin_url,
        homepage_url=user.homepage_url,
        zhihu_url=user.zhihu_url,
        subscribed_topics=[schemas.Topic.from_orm(t) for t in user.subscribed_topics],
        work_exps=_get_work_exps(db, user),
        edu_exps=_get_edu_exps(db, user),
        contributions=contributions,
    )


@router.get("/{uuid}/questions/", response_model=List[schemas.QuestionPreview])
def get_user_questions(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_QUESTIONS_PAGINATION_LIMIT,
        le=MAX_USER_QUESTIONS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get a user's asked questions.
    """
    user = crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    # FIXME: think about more efficient paging mechanism
    return filter_not_none(
        [
            cached_layer.materializer.preview_of_question(question)
            for question in user.questions
            if not question.is_hidden
        ]
    )[skip : skip + limit]


@router.get("/{uuid}/submissions/", response_model=List[schemas.Submission])
def get_user_submissions(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_SUBMISSIONS_PAGINATION_LIMIT,
        le=MAX_USER_SUBMISSIONS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get a user's submissions.
    """
    user = crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return filter_not_none(
        [
            cached_layer.materializer.submission_schema_from_orm(submission)
            for submission in user.submissions
        ]
    )[skip : skip + limit]


@router.get("/{uuid}/articles/", response_model=List[schemas.ArticlePreview])
def get_user_articles(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_ARTICLES_PAGINATION_LIMIT,
        le=MAX_USER_ARTICLES_PAGINATION_LIMIT,
        gt=0,
    ),
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    user = crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return filter_not_none(
        [
            cached_layer.materializer.preview_of_article(article)
            for article in user.articles
        ]
    )[skip : skip + limit]


@router.get(
    "/{uuid}/answers/",
    response_model=Union[
        List[schemas.AnswerPreview], List[schemas.AnswerPreviewForVisitor]
    ],  # type: ignore
)
def get_user_answers(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_ANSWERS_PAGINATION_LIMIT,
        le=MAX_USER_ANSWERS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get a user's authored answers.
    """
    author = crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if author is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return cached_layer.get_authored_answers_for_principal(author)[skip : skip + limit]


@router.get("/{uuid}/work-exps/", response_model=List[schemas.UserWorkExperience])
def get_user_work_exps(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    user = crud.user.get_by_uuid(db, uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return _get_work_exps(db, user)


@router.get("/{uuid}/edu-exps/", response_model=List[schemas.UserEducationExperience])
def get_user_edu_exps(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    user = crud.user.get_by_uuid(db, uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return _get_edu_exps(db, user)


@router.get("/{uuid}/followers/", response_model=List[schemas.UserPreview])
def get_user_followers(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        le=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    user = crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return cached_layer.get_followers(user, skip=skip, limit=limit)


@router.get("/{uuid}/followed/", response_model=List[schemas.UserPreview])
def get_user_followed(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        le=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    user = crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    return cached_layer.get_followed(user, skip=skip, limit=limit)


@router.get("/{uuid}/related/", response_model=List[schemas.UserPreview])
def get_related(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
) -> Any:
    target_user = unwrap(crud.user.get_by_uuid(cached_layer.get_db(), uuid=uuid))
    return cached_layer.get_related_user(target_user)
