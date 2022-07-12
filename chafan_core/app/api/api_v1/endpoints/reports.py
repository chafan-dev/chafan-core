from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType
from chafan_core.app.materialize import check_user_in_site
from chafan_core.utils.base import HTTPException_

router = APIRouter()


@router.post("/", response_model=schemas.Report)
def create_report(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    db: Session = Depends(deps.get_db),
    report_in: schemas.ReportCreate,
) -> Any:
    """
    Create new report authored by the current active user in one of the belonging sites.
    """
    current_user_id = cached_layer.unwrapped_principal_id()
    object_ids = sum(
        int(id is not None)
        for id in [
            report_in.question_uuid,
            report_in.submission_uuid,
            report_in.answer_uuid,
            report_in.comment_uuid,
            report_in.article_uuid,
        ]
    )
    if object_ids != 1:
        raise HTTPException_(
            status_code=400,
            detail="The report has too many or too few object ids.",
        )

    def check_site(site: models.Site) -> None:
        check_user_in_site(
            db,
            site=site,
            user_id=current_user_id,
            op_type=OperationType.WriteSiteComment,
        )

    report = crud.report.create_with_author(
        db, obj_in=report_in, author_id=current_user_id, check_site=check_site
    )
    return cached_layer.materializer.report_schema_from_orm(report)
