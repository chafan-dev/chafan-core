"""Back-compat re-exports only.

Schema shaping: responders/*
Permissions: user_permission
Principal-scoped shaper: infra.principal_view.PrincipalView
  (via RequestContext.materializer / as_principal)

Materializer is an alias of PrincipalView for historical imports.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.infra.principal_view import PrincipalView
import chafan_core.app.user_permission as user_permission

# Historical name — prefer PrincipalView / ctx.materializer / ctx.as_principal.
Materializer = PrincipalView


def get_active_site_profile(
    db: Session, *, site: models.Site, user_id: int
) -> Optional[models.Profile]:
    return user_permission.get_active_site_profile(db, site, user_id)


def user_in_site(
    db: Session,
    *,
    site: models.Site,
    user_id: Optional[int],
    op_type: OperationType,
) -> bool:
    return user_permission.user_in_site(db, site, user_id, op_type)


def check_user_in_site(
    db: Session, *, site: models.Site, user_id: int, op_type: OperationType
) -> None:
    user_permission.check_user_in_site(
        db, site=site, user_id=user_id, op_type=op_type
    )


def check_user_in_channel(current_user: models.User, channel: models.Channel) -> None:
    user_permission.check_user_in_channel(current_user, channel)


def can_read_answer(db: Session, *, answer: models.Answer, principal_id: int) -> bool:
    return user_permission.can_read_answer(
        db, answer=answer, principal_id=principal_id
    )


def visitor_can_read_answer(*, answer: models.Answer) -> bool:
    return user_permission.visitor_can_read_answer(answer=answer)


def can_read_article(*, article: models.Article, principal_id: int) -> bool:
    from chafan_core.app.responders import article as article_responder

    return article_responder.can_read_article(
        article=article, principal_id=principal_id
    )


def visitor_can_read_article(*, article: models.Article) -> bool:
    from chafan_core.app.responders import article as article_responder

    return article_responder.visitor_can_read_article(article=article)


def get_answer_text_preview(answer: models.Answer):
    from chafan_core.app.responders import answer as answer_responder

    return answer_responder.get_answer_text_preview(answer)


def user_schema_from_orm(user: models.User) -> schemas.User:
    from chafan_core.app.responders import user as user_responder

    return user_responder.user_schema_from_orm(user)


def preview_of_question_as_search_hit(question: models.Question):
    from chafan_core.app.responders import question as question_responder

    return question_responder.preview_of_question_as_search_hit(question)


def submission_archive_schema_from_orm(submission: models.SubmissionArchive):
    from chafan_core.app.responders import archives as archives_responder

    return archives_responder.submission_archive_schema_from_orm(submission)


def article_archive_schema_from_orm(article_archive: models.ArticleArchive):
    from chafan_core.app.responders import archives as archives_responder

    return archives_responder.article_archive_schema_from_orm(article_archive)


def answer_archive_schema_from_orm(answer_archive: models.Archive):
    from chafan_core.app.responders import archives as archives_responder

    return archives_responder.answer_archive_schema_from_orm(answer_archive)


def root_route(comment: models.Comment):
    from chafan_core.app.responders.comment import root_route as _root_route

    return _root_route(comment)
