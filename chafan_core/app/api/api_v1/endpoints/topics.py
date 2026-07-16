from typing import Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import topics as topics_service

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.Topic)
def get_topic(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
) -> Any:
    """
    Get topic.
    """
    return topics_service.get_topic(db, uuid)


@router.post("/", response_model=schemas.Topic)
def create_topic(
    *,
    db: Session = Depends(deps.get_db),
    topic_in: schemas.TopicCreate,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Create new topic with name or return existing one.
    TODO: avoid spamming
    """
    return topics_service.create_topic(db, name=topic_in.name)


@router.get("/{uuid}/questions/", response_model=List[schemas.QuestionPreview])
def get_topic_questions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return topics_service.list_topic_questions(
        ctx, uuid=uuid, skip=skip, limit=limit
    )


@router.get("/{uuid}/sub-topics/", response_model=List[schemas.Topic])
def get_sub_topics(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
) -> Any:
    return topics_service.list_sub_topics(db, uuid)
