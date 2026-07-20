"""Content report domain service."""

from __future__ import annotations

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_


def create_report(ctx, *, report_in: schemas.ReportCreate) -> schemas.Report:
    db = ctx.get_db()
    current_user_id = ctx.unwrapped_principal_id()
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
    return misc_responder.report_schema_from_orm(ctx.materializer, report)
