"""Archive ORM → API schema shaping (no principal)."""

from __future__ import annotations

from typing import Any, Dict

from chafan_core.app import models, schemas
from chafan_core.app.schemas.answer_archive import AnswerArchiveInDB
from chafan_core.app.schemas.article_archive import ArticleArchiveInDB
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import map_


def submission_archive_schema_from_orm(
    submission: models.SubmissionArchive,
) -> schemas.SubmissionArchive:
    d: Dict[str, Any] = {}
    d["id"] = submission.id
    d["created_at"] = submission.created_at
    d["title"] = submission.title
    d["topic_uuids"] = submission.topic_uuids
    d["url"] = submission.submission.url if submission.submission else None
    if submission.description is not None:
        d["desc"] = RichText(
            source=submission.description,
            rendered_text=submission.description_text,
            editor=submission.description_editor,
        )
    else:
        d["desc"] = None
    return schemas.SubmissionArchive(**d)


def article_archive_schema_from_orm(
    article_archive: models.ArticleArchive,
) -> schemas.ArticleArchive:
    base = ArticleArchiveInDB.from_orm(article_archive)
    d = base.dict()
    d["content"] = RichText(
        source=article_archive.body,
        editor=article_archive.editor,
    )
    return schemas.ArticleArchive(**d)


def answer_archive_schema_from_orm(
    answer_archive: models.Archive,
) -> schemas.AnswerArchive:
    base = AnswerArchiveInDB.from_orm(answer_archive)
    d = base.dict()
    d["content"] = RichText(
        source=answer_archive.body,
        editor=answer_archive.editor,
    )
    return schemas.AnswerArchive(**d)


def question_archive_schema_from_orm(
    mat, archive: models.QuestionArchive
) -> schemas.QuestionArchive:
    base = schemas.QuestionArchiveInDB.from_orm(archive)
    d = base.dict()
    d["editor"] = map_(archive.editor, mat.preview_of_user)
    if archive.description is not None:
        d["desc"] = RichText(
            source=archive.description,
            editor=archive.description_editor,
            rendered_text=archive.description_text,
        )
    return schemas.QuestionArchive(**d)
