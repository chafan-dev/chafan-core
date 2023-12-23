from typing import Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.utils.base import HTTPException_, filter_not_none

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
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exists in the system.",
        )
    return topic


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
    return crud.topic.get_or_create(db, name=topic_in.name)


@router.get("/{uuid}/questions/", response_model=List[schemas.QuestionPreview])
def get_topic_questions(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    db = cached_layer.get_db()
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exists in the system.",
        )
    # FIXME: expensive
    questions: List[models.Question] = topic.questions[skip : (skip + limit)]
    return filter_not_none(
        [
            cached_layer.materializer.preview_of_question(question)
            for question in questions
            if not question.is_hidden
        ]
    )


@router.get("/{uuid}/sub-topics/", response_model=List[schemas.Topic])
def get_sub_topics(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
) -> Any:
    topic = crud.topic.get_by_uuid(db, uuid=uuid)
    if topic is None:
        raise HTTPException_(
            status_code=400,
            detail="The topic doesn't exists in the system.",
        )
    return topic.child_topics
