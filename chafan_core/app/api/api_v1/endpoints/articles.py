import datetime
from typing import Any, List, Optional, Union

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.param_functions import Query
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, view_counters
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import client_ip, run_dramatiq_task
from chafan_core.app.config import settings
from chafan_core.app.endpoint_utils import check_writing_session
from chafan_core.app.materialize import article_archive_schema_from_orm
from chafan_core.app.schemas.event import EventInternal, UpvoteArticleInternal
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import ContentVisibility, HTTPException_
from chafan_core.utils.constants import MAX_ARCHIVE_PAGINATION_LIMIT

router = APIRouter()


@router.get("/{uuid}", response_model=Union[schemas.Article, schemas.ArticleForVisitor])
def get_article(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    current_user_id = cached_layer.principal_id
    article = crud.article.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    data: Optional[Union[schemas.Article, schemas.ArticleForVisitor]] = None
    if current_user_id:
        data = cached_layer.materializer.article_schema_from_orm(article)
    else:
        if article.visibility != ContentVisibility.ANYONE:
            raise HTTPException_(
                status_code=400,
                detail="The article doesn't exists in the system.",
            )
        data = cached_layer.materializer.article_for_visitor_schema_from_orm(article)
    if data is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    return data


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
def bump_views_counter(
    *,
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    if current_user_id:
        view_counters.add_view(uuid, "article", current_user_id)
    return schemas.GenericResponse()


@router.delete("/{uuid}", response_model=schemas.GenericResponse)
def delete_article(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    if article.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    crud.article.delete_forever(db, article=article)
    return schemas.GenericResponse()


@router.get("/{uuid}/draft", response_model=schemas.article.ArticleDraft)
def get_article_draft(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get article's draft body as its author.
    """
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    if current_user_id != article.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    content = None
    if article.body_draft:
        content = RichText(
            source=article.body_draft,
            editor=article.draft_editor,
        )
    return schemas.article.ArticleDraft(
        title_draft=article.title_draft,
        draft_saved_at=article.draft_saved_at,
        content_draft=content,
    )


@router.delete("/{uuid}/draft", response_model=schemas.article.ArticleDraft)
def delete_article_draft(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    if current_user_id != article.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    content_draft = None
    if article.body_draft:
        assert article.draft_editor
        content_draft = RichText(
            source=article.body_draft,
            editor=article.draft_editor,
        )
    data = schemas.article.ArticleDraft(
        title_draft=article.title_draft,
        draft_saved_at=article.draft_saved_at,
        content_draft=content_draft,
    )
    article.title_draft = None
    article.body_draft = None
    article.draft_saved_at = None
    db.add(article)
    db.commit()
    return data


@router.post("/", response_model=schemas.Article)
def create_article(
    request: Request,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    article_in: schemas.ArticleCreate,
) -> Any:
    """
    Create new article authored by the current user in one of the belonging sites.
    """
    current_user = cached_layer.get_current_active_user()
    cached_layer.get_db()
    crud.audit_log.create_with_user(
        cached_layer.get_db(),
        ipaddr=client_ip(request),
        user_id=current_user.id,
        api="post article",
        request_info={"article_in": jsonable_encoder(article_in)},
    )

    if current_user.remaining_coins < settings.CREATE_ARTICLE_COIN_DEDUCTION:
        raise HTTPException_(
            status_code=400,
            detail="Insuffient coins.",
        )
    check_writing_session(article_in.writing_session_uuid)
    article_column = crud.article_column.get_by_uuid(
        cached_layer.get_db(), uuid=article_in.article_column_uuid
    )
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article column doesn't exist.",
        )
    if article_column.owner_id != current_user.id:
        raise HTTPException_(
            status_code=400,
            detail="The article column is not owned by current user.",
        )
    new_article = crud.article.create_with_author(
        cached_layer.get_db(), obj_in=article_in, author_id=current_user.id
    )
    if new_article.is_published:
        from chafan_core.app.task import postprocess_new_article

        run_dramatiq_task(postprocess_new_article, new_article.id)
    data = cached_layer.materializer.article_schema_from_orm(new_article)
    assert data is not None
    return data


@router.put("/{uuid}", response_model=schemas.Article)
def update_article(
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    article_in: schemas.ArticleUpdate,
) -> Any:
    current_user_id = cached_layer.unwrapped_principal_id()
    crud.audit_log.create_with_user(
        cached_layer.get_db(),
        ipaddr=client_ip(request),
        user_id=current_user_id,
        api="post article",
        request_info={"article_in": jsonable_encoder(article_in), "uuid": uuid},
    )

    article = crud.article.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    if article.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )

    article_in_dict = article_in.dict(exclude_none=True)

    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    if article_in.is_draft:
        article_in_dict["body_draft"] = article_in.updated_content.source
        article_in_dict["title_draft"] = article_in.updated_title
        article_in_dict["draft_editor"] = article_in.updated_content.editor
        del article_in_dict["updated_content"]
        del article_in_dict["updated_title"]
        article_in_dict["draft_saved_at"] = utc_now
    else:
        if article.is_published:
            assert article.updated_at is not None
            archive = models.ArticleArchive(
                article_id=article.id,
                title=article.title,
                body=article.body,
                editor=article.editor,  # type: ignore
                created_at=article.updated_at,
            )
            cached_layer.get_db().add(archive)
            article.archives.append(archive)
            cached_layer.get_db().commit()
        if not article.is_published:
            article_in_dict["initial_published_at"] = utc_now
        article_in_dict["is_published"] = True
        article_in_dict["updated_at"] = utc_now
        article_in_dict["title"] = article_in.updated_title
        article_in_dict["body"] = article_in.updated_content.source
        article_in_dict["body_text"] = article_in.updated_content.rendered_text
        article_in_dict["body_draft"] = None
        article_in_dict["title_draft"] = None
        article_in_dict["draft_saved_at"] = None

    was_published = article.is_published
    article = crud.article.update_checked(
        cached_layer.get_db(), db_obj=article, obj_in=article_in_dict
    )

    if article.is_published:
        from chafan_core.app.task import postprocess_updated_article

        run_dramatiq_task(postprocess_updated_article, article.id, was_published)
    data = cached_layer.materializer.article_schema_from_orm(article)
    assert data is not None
    return data


@router.put("/{uuid}/topics/", response_model=schemas.GenericResponse)
def update_article_topics(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    topics_in: schemas.ArticleTopicsUpdate,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    if article.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    new_topics = []
    for topic_uuid in topics_in.topic_uuids:
        topic = crud.topic.get_by_uuid(db, uuid=topic_uuid)
        if topic is None:
            raise HTTPException_(
                status_code=400,
                detail="The topic doesn't exist.",
            )
        new_topics.append(topic)
    crud.article.update_topics(db, db_obj=article, new_topics=new_topics)
    return schemas.GenericResponse()


@router.get("/{uuid}/archives/", response_model=List[schemas.ArticleArchive])
def get_article_archives(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_ARCHIVE_PAGINATION_LIMIT, le=MAX_ARCHIVE_PAGINATION_LIMIT, gt=0
    ),
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get answer's archives as its author.
    """
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    if article.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return [
        article_archive_schema_from_orm(a)
        for a in article.archives[skip : (skip + limit)]
    ]


@router.post("/{uuid}/upvotes/", response_model=schemas.ArticleUpvotes)
def upvote_article(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    upvoted = (
        db.query(models.ArticleUpvotes)
        .filter_by(article_id=article.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if upvoted:
        raise HTTPException_(
            status_code=400,
            detail="You can't upvote twice.",
        )
    if current_user.id == article.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Author can't upvote authored article.",
        )
    if current_user.remaining_coins < settings.UPVOTE_ARTICLE_COIN_DEDUCTION:
        raise HTTPException_(
            status_code=400,
            detail="Insuffient coins.",
        )
    upvoted_before = (
        db.query(models.ArticleUpvotes)
        .filter_by(article_id=article.id, voter_id=current_user.id)
        .first()
        is not None
    )
    # Don't swap the statements before and after!
    article = crud.article.upvote(db, db_obj=article, voter=current_user)
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    if not upvoted_before:
        crud.coin_payment.make_payment(
            db,
            obj_in=schemas.CoinPaymentCreate(
                payee_id=article.author_id,
                amount=settings.UPVOTE_ARTICLE_COIN_DEDUCTION,
                event_json=EventInternal(
                    created_at=utc_now,
                    content=UpvoteArticleInternal(
                        subject_id=current_user.id,
                        article_id=article.id,
                    ),
                ).json(),
            ),
            payer=current_user,
            payee=article.author,
        )
    db.commit()
    db.refresh(article)
    valid_upvotes = (
        db.query(models.ArticleUpvotes)
        .filter_by(article_id=article.id, cancelled=False)
        .count()
    )
    return schemas.ArticleUpvotes(
        article_uuid=article.uuid, count=valid_upvotes, upvoted=True
    )


@router.delete("/{uuid}/upvotes/", response_model=schemas.ArticleUpvotes)
def cancel_upvote_article(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    article = crud.article.get_by_uuid(db, uuid=uuid)
    if article is None:
        raise HTTPException_(
            status_code=400,
            detail="The article doesn't exists in the system.",
        )
    upvoted = (
        db.query(models.ArticleUpvotes)
        .filter_by(article_id=article.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if not upvoted:
        raise HTTPException_(
            status_code=400,
            detail="You haven't voted yet.",
        )
    article = crud.article.cancel_upvote(db, db_obj=article, voter=current_user)
    db.commit()
    db.refresh(article)
    valid_upvotes = (
        db.query(models.ArticleUpvotes)
        .filter_by(article_id=article.id, cancelled=False)
        .count()
    )
    return schemas.ArticleUpvotes(
        article_uuid=article.uuid, count=valid_upvotes, upvoted=False
    )
