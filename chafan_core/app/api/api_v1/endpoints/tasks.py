import datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import run_dramatiq_task
from chafan_core.app.endpoint_utils import get_site
from chafan_core.utils.base import HTTPException_, TaskStatus

router = APIRouter()


def _create_task(
    db: Session, *, current_user: models.User, task_definition: schemas.TaskDefinition
) -> models.Task:
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    task = models.Task(
        created_at=utc_now,
        initiator_id=current_user.id,
        task_definition=jsonable_encoder(task_definition),
        status=TaskStatus.PENDING,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/", response_model=schemas.Task)
def create_task(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    task_definition: schemas.TaskDefinition,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    if task_definition.task_type == "super_broadcast":
        if not current_user.is_superuser:
            raise HTTPException_(
                status_code=400,
                detail="Unauthorized.",
            )
        task = _create_task(
            db, current_user=current_user, task_definition=task_definition
        )
        from chafan_core.app.task import super_broadcast

        run_dramatiq_task(super_broadcast, task.id, task_definition.message)
        return cached_layer.materializer.task_schema_from_orm(task)
    elif task_definition.task_type == "site_broadcast":
        site = get_site(db, task_definition.to_members_of_site_uuid)
        if site is None:
            raise HTTPException_(
                status_code=400,
                detail="Invalid site UUID.",
            )
        if site.moderator_id != current_user.id:
            raise HTTPException_(
                status_code=400,
                detail="Unauthorized.",
            )
        submission = crud.submission.get_by_uuid(
            db, uuid=task_definition.submission_uuid
        )
        if submission is None:
            raise HTTPException_(
                status_code=400,
                detail="Invalid submission UUID.",
            )
        task = _create_task(
            db, current_user=current_user, task_definition=task_definition
        )
        from chafan_core.app.task import site_broadcast

        run_dramatiq_task(site_broadcast, task.id, submission.id, site.id)
        return cached_layer.materializer.task_schema_from_orm(task)
    else:
        raise HTTPException_(
            status_code=400,
            detail="Invalid task type.",
        )
