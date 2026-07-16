"""Submission suggestion and answer suggest-edit schema shaping."""

from __future__ import annotations

from typing import Optional

from chafan_core.app import crud, models, schemas
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import unwrap


def submission_suggestion_schema_from_orm(
    mat, submission_suggestion: models.SubmissionSuggestion
) -> Optional[schemas.SubmissionSuggestion]:
    base = schemas.SubmissionSuggestionInDB.from_orm(submission_suggestion)
    d = base.dict()
    d["author"] = mat.preview_of_user(submission_suggestion.author)
    submission = mat.submission_schema_from_orm(submission_suggestion.submission)
    if not submission:
        return None
    d["submission"] = submission
    if submission_suggestion.topic_uuids:
        d["topics"] = [
            schemas.Topic.from_orm(
                unwrap(crud.topic.get_by_uuid(mat.get_db(), uuid=uuid))
            )
            for uuid in submission_suggestion.topic_uuids
        ]
    if submission_suggestion.description:
        d["desc"] = RichText(
            source=submission_suggestion.description,
            rendered_text=submission_suggestion.description_text,
            editor=submission_suggestion.description_editor,
        )
    else:
        d["desc"] = None
    return schemas.SubmissionSuggestion(**d)


def answer_suggest_edit_schema_from_orm(
    mat, answer_suggest_edit: models.AnswerSuggestEdit
) -> Optional[schemas.AnswerSuggestEdit]:
    from chafan_core.app.responders import answer as answer_responder

    base = schemas.AnswerSuggestEditInDB.from_orm(answer_suggest_edit)
    d = base.dict()
    d["author"] = mat.preview_of_user(answer_suggest_edit.author)
    # Prefer broker (RequestContext) when present for full answer shaping.
    ctx = getattr(mat, "broker", mat)
    principal_id = getattr(ctx, "principal_id", None)
    answer = answer_responder.answer_schema_from_orm(
        ctx, answer_suggest_edit.answer, principal_id
    )
    if not answer:
        return None
    d["answer"] = answer
    if answer_suggest_edit.body:
        assert answer_suggest_edit.body_editor
        d["body_rich_text"] = RichText(
            source=answer_suggest_edit.body,
            rendered_text=answer_suggest_edit.body_text,
            editor=answer_suggest_edit.body_editor,
        )
    else:
        d["body_rich_text"] = None
    return schemas.AnswerSuggestEdit(**d)
