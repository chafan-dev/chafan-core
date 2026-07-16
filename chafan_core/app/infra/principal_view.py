"""Principal-scoped schema shaper (plain previews + responder dispatch).

Used as RequestContext.materializer and RequestContext.as_principal(id).
Shares the parent context's db/redis; holds its own principal_id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from chafan_core.app import models, schemas
    from chafan_core.app.infra.request_context import RequestContext
    from chafan_core.app.schemas.event import Event
    from chafan_core.app.schemas.notification import Notification


class PrincipalView:
    """Schema shaper for one principal viewing content.

    Nested author previews use plain (non-social) user previews. Permission
    gates use this principal_id.
    """

    def __init__(self, ctx: "RequestContext", principal_id: Optional[int]) -> None:
        self._ctx = ctx
        # responders/event and legacy code use .broker for get_db()
        self.broker = ctx
        self.principal_id = principal_id
        self._principal: Optional["models.User"] = None
        if principal_id is not None:
            from chafan_core.app import crud

            self._principal = crud.user.get(ctx.get_db(), id=principal_id)
        self.principal = self._principal

    def get_db(self) -> Session:
        return self._ctx.get_db()

    def get_redis(self):
        return self._ctx.get_redis()

    def try_get_current_user(self) -> Optional["models.User"]:
        return self.principal

    def preview_of_user(self, user: "models.User") -> "schemas.UserPreview":
        from chafan_core.app.responders import user as user_responder

        return user_responder.plain_preview_of_user(user)

    def site_schema_from_orm(self, site: "models.Site") -> "schemas.Site":
        import chafan_core.app.responders as responders

        return responders.site.site_schema_from_orm(self, site)

    def get_user_article_column_subscription(
        self, article_column: "models.ArticleColumn"
    ) -> "schemas.UserArticleColumnSubscription":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.get_user_article_column_subscription(
            self, article_column
        )

    def article_column_schema_from_orm(
        self, article_column: "models.ArticleColumn"
    ) -> "schemas.ArticleColumn":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.article_column_schema_from_orm(self, article_column)

    def preview_of_question(
        self, question: "models.Question"
    ) -> Optional["schemas.QuestionPreview"]:
        import chafan_core.app.responders as responders

        return responders.question.preview_of_question(self, question)

    def preview_of_question_for_visitor(
        self, question: "models.Question"
    ) -> Optional["schemas.QuestionPreview"]:
        return self.preview_of_question(question)

    def get_answer_preview_base(
        self, answer: "models.Answer"
    ) -> "schemas.answer.AnswerPreviewBase":
        from chafan_core.app.responders import answer as answer_responder

        return answer_responder.answer_preview_base(self, answer)

    def preview_of_answer(
        self, answer: "models.Answer"
    ) -> Optional["schemas.AnswerPreview"]:
        from chafan_core.app.responders import answer as answer_responder

        return answer_responder.preview_of_answer(self, answer)

    def preview_of_answer_for_visitor(
        self, answer: "models.Answer"
    ) -> Optional["schemas.AnswerPreview"]:
        return self.preview_of_answer(answer)

    def preview_of_article(
        self, article: "models.Article"
    ) -> Optional["schemas.ArticlePreview"]:
        from chafan_core.app.responders import article as article_responder

        return article_responder.preview_of_article(self, article)

    def message_schema_from_orm(self, message: "models.Message") -> "schemas.Message":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.message_schema_from_orm(self, message)

    def form_schema_from_orm(self, form: "models.Form") -> "schemas.Form":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.form_schema_from_orm(self, form)

    def webhook_schema_from_orm(self, webhook: "models.Webhook") -> "schemas.Webhook":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.webhook_schema_from_orm(self, webhook)

    def form_response_schema_from_orm(
        self, form_response: "models.FormResponse"
    ) -> "schemas.FormResponse":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.form_response_schema_from_orm(self, form_response)

    def profile_schema_from_orm(self, profile: "models.Profile") -> "schemas.Profile":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.profile_schema_from_orm(self, profile)

    def question_archive_schema_from_orm(
        self, archive: "models.QuestionArchive"
    ) -> "schemas.QuestionArchive":
        from chafan_core.app.responders import archives as archives_responder

        return archives_responder.question_archive_schema_from_orm(self, archive)

    def invitation_link_schema_from_orm(
        self, invitation_link: "models.InvitationLink"
    ) -> "schemas.InvitationLink":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.invitation_link_schema_from_orm(self, invitation_link)

    def reward_schema_from_orm(self, reward: "models.Reward") -> "schemas.Reward":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.reward_schema_from_orm(self, reward)

    def application_schema_from_orm(
        self, application: "models.Application"
    ) -> "schemas.Application":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.application_schema_from_orm(self, application)

    def audit_log_schema_from_orm(
        self, audit_log: "models.AuditLog"
    ) -> "schemas.AuditLog":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.audit_log_schema_from_orm(self, audit_log)

    def task_schema_from_orm(self, task: "models.Task") -> "schemas.Task":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.task_schema_from_orm(self, task)

    def materialize_event(self, event_internal_json: str) -> Optional["Event"]:
        from chafan_core.app.responders import event as event_responder

        return event_responder.materialize_event(self, event_internal_json)

    def submission_schema_from_orm(
        self, submission: "models.Submission"
    ) -> Optional["schemas.Submission"]:
        import chafan_core.app.responders as responders

        return responders.submission.submission_schema_from_orm(self, submission)

    def submission_for_visitor_schema_from_orm(
        self, submission: "models.Submission"
    ) -> Optional["schemas.Submission"]:
        return self.submission_schema_from_orm(submission)

    def notification_schema_from_orm(
        self, notification: "models.Notification"
    ) -> Optional["Notification"]:
        from chafan_core.app.responders import event as event_responder

        return event_responder.notification_schema_from_orm(self, notification)

    def submission_suggestion_schema_from_orm(
        self, submission_suggestion: "models.SubmissionSuggestion"
    ) -> Optional["schemas.SubmissionSuggestion"]:
        from chafan_core.app.responders import suggestions as suggestions_responder

        return suggestions_responder.submission_suggestion_schema_from_orm(
            self, submission_suggestion
        )

    def answer_suggest_edit_schema_from_orm(
        self, answer_suggest_edit: "models.AnswerSuggestEdit"
    ) -> Optional["schemas.AnswerSuggestEdit"]:
        from chafan_core.app.responders import suggestions as suggestions_responder

        return suggestions_responder.answer_suggest_edit_schema_from_orm(
            self, answer_suggest_edit
        )

    def comment_schema_from_orm(
        self, comment: "models.Comment"
    ) -> Optional["schemas.Comment"]:
        from chafan_core.app.responders import comment as comment_responder

        return comment_responder.comment_schema_from_orm(self, comment)

    def get_question_upvotes(
        self, question: "models.Question"
    ) -> "schemas.QuestionUpvotes":
        import chafan_core.app.responders as responders

        return responders.question.get_question_upvotes(
            self.get_db(), question, self.principal_id
        )

    def channel_schema_from_orm(self, channel: "models.Channel") -> "schemas.Channel":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.channel_schema_from_orm(self, channel)

    def report_schema_from_orm(self, report: "models.Report") -> "schemas.Report":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.report_schema_from_orm(self, report)

    def feedback_schema_from_orm(self, f: "models.Feedback") -> "schemas.Feedback":
        from chafan_core.app.responders import misc as misc_responder

        return misc_responder.feedback_schema_from_orm(self, f)
