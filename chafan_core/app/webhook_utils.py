from typing import Literal, NamedTuple, Union

import requests
import sentry_sdk
from fastapi.encoders import jsonable_encoder
from pydantic.main import BaseModel
from pydantic.tools import parse_obj_as

from chafan_core.app import models
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import is_dev
from chafan_core.app.schemas import AnswerPreviewForVisitor, QuestionPreviewForVisitor
from chafan_core.app.schemas.submission import SubmissionForVisitor
from chafan_core.app.schemas.webhook import WebhookEventSpec, WebhookSiteEvent


class SiteNewAnswerEvent(NamedTuple):
    answer: models.Answer


class SiteNewQuestionEvent(NamedTuple):
    question: models.Question


class SiteNewSubmissionEvent(NamedTuple):
    submission: models.Submission


class NewAnswerEventDetails(BaseModel):
    sub_type: Literal["new_answer"] = "new_answer"
    answer_preview: AnswerPreviewForVisitor


class NewQuestionEventDetails(BaseModel):
    sub_type: Literal["new_question"] = "new_question"
    question_preview: QuestionPreviewForVisitor


class NewSubmissionEventDetails(BaseModel):
    sub_type: Literal["new_submission"] = "new_submission"
    submission: SubmissionForVisitor


class WebhookEvent(BaseModel):
    type: Literal["site_event"]
    details: Union[
        NewAnswerEventDetails, NewQuestionEventDetails, NewSubmissionEventDetails
    ]


def _post_webhook(webhook: models.Webhook, webhook_event: WebhookEvent) -> None:
    try:
        r = requests.post(
            webhook.callback_url,
            json={
                "secret": webhook.secret,
                "event": jsonable_encoder(webhook_event),
            },
            timeout=5,
        )
        if is_dev():
            print("Response: " + r.text)
    except Exception as e:
        sentry_sdk.capture_exception(e)


def call_webhook(
    cached_layer: CachedLayer,
    webhook: models.Webhook,
    event: Union[SiteNewAnswerEvent, SiteNewQuestionEvent, SiteNewSubmissionEvent],
) -> None:
    if not webhook.enabled:
        return
    event_spec_content = parse_obj_as(WebhookEventSpec, webhook.event_spec).content
    if isinstance(event, SiteNewAnswerEvent):
        if (
            isinstance(event_spec_content, WebhookSiteEvent)
            and event_spec_content.new_answer
        ):
            answer_preview = cached_layer.materializer.preview_of_answer_for_visitor(
                event.answer
            )
            if answer_preview:
                _post_webhook(
                    webhook,
                    WebhookEvent(
                        type="site_event",
                        details=NewAnswerEventDetails(answer_preview=answer_preview),
                    ),
                )
    elif isinstance(event, SiteNewQuestionEvent):
        if (
            isinstance(event_spec_content, WebhookSiteEvent)
            and event_spec_content.new_question
        ):
            question_preview = (
                cached_layer.materializer.preview_of_question_for_visitor(
                    event.question
                )
            )
            if question_preview:
                _post_webhook(
                    webhook,
                    WebhookEvent(
                        type="site_event",
                        details=NewQuestionEventDetails(
                            question_preview=question_preview
                        ),
                    ),
                )
    elif isinstance(event, SiteNewSubmissionEvent):
        if (
            isinstance(event_spec_content, WebhookSiteEvent)
            and event_spec_content.new_submission
        ):
            submission = (
                cached_layer.materializer.submission_for_visitor_schema_from_orm(
                    event.submission
                )
            )
            if submission:
                _post_webhook(
                    webhook,
                    WebhookEvent(
                        type="site_event",
                        details=NewSubmissionEventDetails(submission=submission),
                    ),
                )
