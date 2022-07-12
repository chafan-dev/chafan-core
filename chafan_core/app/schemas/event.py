import datetime
from typing import Literal, Mapping, Optional, Union

from pydantic import BaseModel

from chafan_core.utils.base import map_
from chafan_core.app.config import settings
from chafan_core.app.schemas.answer import AnswerPreview, QuestionPreview
from chafan_core.app.schemas.answer_suggest_edit import AnswerSuggestEdit
from chafan_core.app.schemas.article import ArticlePreview
from chafan_core.app.schemas.article_column import ArticleColumn
from chafan_core.app.schemas.channel import Channel
from chafan_core.app.schemas.comment import Comment
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.reward import Reward
from chafan_core.app.schemas.site import Site
from chafan_core.app.schemas.submission import Submission
from chafan_core.app.schemas.submission_suggestion import SubmissionSuggestion
from chafan_core.utils.validators import CaseInsensitiveEmailStr

StringArg = Union[str, Optional[str], int, Optional[CaseInsensitiveEmailStr]]


def display_name(user: UserPreview) -> str:
    if user.full_name:
        return user.full_name
    return "@" + user.handle


def server_host_link(path: str, text: str) -> str:
    return f'<a style="color: #1976d2; text-decoration: none" href="{settings.SERVER_HOST}{path}">{text}</a>'


def user_link(user: UserPreview) -> str:
    return server_host_link(f"/users/{user.handle}", display_name(user))


def question_link(question: QuestionPreview) -> str:
    return server_host_link(f"/questions/{question.uuid}", question.title)


def submission_link(submission: Submission) -> str:
    return server_host_link(f"/submissions/{submission.uuid}", submission.title)


def submission_suggestion_link(submission_suggestion: SubmissionSuggestion) -> str:
    return server_host_link(
        f"/submissions/{submission_suggestion.submission.uuid}/suggestions/{submission_suggestion.uuid}",
        submission_suggestion.submission.title,
    )


def answer_suggest_edit_link(answer_suggest_edit: AnswerSuggestEdit) -> str:
    return server_host_link(
        f"/questions/{answer_suggest_edit.answer.question.uuid}/answers/{answer_suggest_edit.answer.uuid}/suggestions/{answer_suggest_edit.uuid}",
        answer_suggest_edit.answer.question.title,
    )


def article_link(article: ArticlePreview) -> str:
    return server_host_link(f"/articles/{article.uuid}", article.title)


def article_column_link(article_column: ArticleColumn) -> str:
    return server_host_link(
        f"/article-columns/{article_column.uuid}", article_column.name
    )


def answer_link(answer: AnswerPreview) -> str:
    return server_host_link(
        f"/questions/{answer.question.uuid}/answers/{answer.uuid}", answer.body
    )


def site_link(site: Site) -> str:
    return server_host_link(f"/sites/{site.uuid}", site.name)


def channel_link(channel: Channel) -> str:
    return server_host_link(f"/channels/{channel.id}", channel.name)


def comment_short_or_link(comment: Comment) -> str:
    if comment.content.rendered_text:
        comment_body = comment.content.rendered_text
    else:
        comment_body = comment.content.source
    if len(comment_body) > 20:
        comment_body = comment_body[:20] + "..."
    if comment.root_route is None:
        return comment_body
    return server_host_link(
        f"{comment.root_route}/comments/{comment.uuid}", comment_body
    )


class CreateQuestion(BaseModel):
    verb: Literal["create_question"] = "create_question"
    subject: UserPreview
    question: QuestionPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "question": question_link(self.question),
        }


class CreateQuestionInternal(BaseModel):
    verb: Literal["create_question"] = "create_question"
    subject_id: int
    question_id: int


class CreateSubmission(BaseModel):
    verb: Literal["create_submission"] = "create_submission"
    subject: UserPreview
    submission: Submission

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "submission": submission_link(self.submission),
        }


class CreateSubmissionInternal(BaseModel):
    verb: Literal["create_submission"] = "create_submission"
    subject_id: int
    submission_id: int


class CreateSubmissionSuggestion(BaseModel):
    verb: Literal["create_submission_suggestion"] = "create_submission_suggestion"
    subject: UserPreview
    submission_suggestion: SubmissionSuggestion

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "submission_suggestion": submission_suggestion_link(
                self.submission_suggestion
            ),
        }


class CreateSubmissionSuggestionInternal(BaseModel):
    verb: Literal["create_submission_suggestion"] = "create_submission_suggestion"
    subject_id: int
    submission_suggestion_id: int


class AcceptSubmissionSuggestion(BaseModel):
    verb: Literal["accept_submission_suggestion"] = "accept_submission_suggestion"
    subject: UserPreview
    submission_suggestion: SubmissionSuggestion

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "submission_suggestion": submission_suggestion_link(
                self.submission_suggestion
            ),
        }


class AcceptSubmissionSuggestionInternal(BaseModel):
    verb: Literal["accept_submission_suggestion"] = "accept_submission_suggestion"
    subject_id: int
    submission_suggestion_id: int


class CreateAnswerSuggestEdit(BaseModel):
    verb: Literal["create_answer_suggest_edit"] = "create_answer_suggest_edit"
    subject: UserPreview
    answer_suggest_edit: AnswerSuggestEdit

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "answer_suggest_edit": answer_suggest_edit_link(self.answer_suggest_edit),
        }


class CreateAnswerSuggestEditInternal(BaseModel):
    verb: Literal["create_answer_suggest_edit"] = "create_answer_suggest_edit"
    subject_id: int
    answer_suggest_edit_id: int


class AcceptAnswerSuggestEdit(BaseModel):
    verb: Literal["accept_answer_suggest_edit"] = "accept_answer_suggest_edit"
    subject: UserPreview
    answer_suggest_edit: AnswerSuggestEdit

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "answer_suggest_edit": answer_suggest_edit_link(self.answer_suggest_edit),
        }


class AcceptAnswerSuggestEditInternal(BaseModel):
    verb: Literal["accept_answer_suggest_edit"] = "accept_answer_suggest_edit"
    subject_id: int
    answer_suggest_edit_id: int


class CreateArticle(BaseModel):
    verb: Literal["create_article"] = "create_article"
    subject: UserPreview
    article: ArticlePreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "article": article_link(self.article),
        }


class CreateArticleInternal(BaseModel):
    verb: Literal["create_article"] = "create_article"
    subject_id: int
    article_id: int


class AnswerQuestion(BaseModel):
    verb: Literal["answer_question"] = "answer_question"
    subject: UserPreview
    answer: AnswerPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "answer": answer_link(self.answer),
            "question": question_link(self.answer.question),
        }


class AnswerQuestionInternal(BaseModel):
    verb: Literal["answer_question"] = "answer_question"
    subject_id: int
    answer_id: int


class AnswerUpdateInternal(BaseModel):
    verb: Literal["answer_update"] = "answer_update"
    subject_id: int
    answer_id: int


class AnswerUpdate(BaseModel):
    verb: Literal["answer_update"] = "answer_update"
    subject: UserPreview
    answer: AnswerPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "answer": answer_link(self.answer),
            "question": question_link(self.answer.question),
        }


class CommentQuestion(BaseModel):
    verb: Literal["comment_question"] = "comment_question"
    subject: UserPreview
    comment: Comment
    question: QuestionPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "comment": comment_short_or_link(self.comment),
            "question": question_link(self.question),
        }


class CommentQuestionInternal(BaseModel):
    verb: Literal["comment_question"] = "comment_question"
    subject_id: int
    comment_id: int
    question_id: int


class EditQuestion(BaseModel):
    verb: Literal["edit_question"] = "edit_question"
    subject: UserPreview
    question: QuestionPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "question": question_link(self.question),
        }


class EditQuestionInternal(BaseModel):
    verb: Literal["edit_question"] = "edit_question"
    subject_id: int
    question_id: int


class CommentSubmission(BaseModel):
    verb: Literal["comment_submission"] = "comment_submission"
    subject: UserPreview
    comment: Comment
    submission: Submission

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "comment": comment_short_or_link(self.comment),
            "submission": submission_link(self.submission),
        }


class CommentSubmissionInternal(BaseModel):
    verb: Literal["comment_submission"] = "comment_submission"
    subject_id: int
    comment_id: int
    submission_id: int


class CreateAnswerQuestionRewardInternal(BaseModel):
    verb: Literal["create_answer_question_reward"] = "create_answer_question_reward"
    subject_id: int
    reward_id: int


class CreateAnswerQuestionReward(BaseModel):
    verb: Literal["create_answer_question_reward"] = "create_answer_question_reward"
    subject: UserPreview
    reward: Reward
    question: QuestionPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "reward_coin_amount": self.reward.coin_amount,
            "question": question_link(self.question),
        }


class ClaimAnswerQuestionRewardInternal(BaseModel):
    verb: Literal["claim_answer_question_reward"] = "claim_answer_question_reward"
    subject_id: int
    reward_id: int


class ClaimAnswerQuestionReward(BaseModel):
    verb: Literal["claim_answer_question_reward"] = "claim_answer_question_reward"
    subject: UserPreview
    reward: Reward
    question: QuestionPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "reward_coin_amount": self.reward.coin_amount,
            "question": question_link(self.question),
        }


class CommentArticle(BaseModel):
    verb: Literal["comment_article"] = "comment_article"
    subject: UserPreview
    comment: Comment
    article: ArticlePreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "comment": comment_short_or_link(self.comment),
            "article": article_link(self.article),
        }


class CommentArticleInternal(BaseModel):
    verb: Literal["comment_article"] = "comment_article"
    subject_id: int
    comment_id: int
    article_id: int


class ReplyComment(BaseModel):
    verb: Literal["reply_comment"] = "reply_comment"
    subject: UserPreview
    reply: Comment
    parent_comment: Comment

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "reply": comment_short_or_link(self.reply),
            "parent_comment": comment_short_or_link(self.parent_comment),
        }


class ReplyCommentInternal(BaseModel):
    verb: Literal["reply_comment"] = "reply_comment"
    subject_id: int
    reply_id: int
    parent_comment_id: int


class MentionedInComment(BaseModel):
    verb: Literal["mentioned_in_comment"] = "mentioned_in_comment"
    subject: UserPreview
    comment: Comment

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "comment": comment_short_or_link(self.comment),
        }


class MentionedInCommentInternal(BaseModel):
    verb: Literal["mentioned_in_comment"] = "mentioned_in_comment"
    subject_id: int
    comment_id: int


class InviteAnswer(BaseModel):
    verb: Literal["invite_answer"] = "invite_answer"
    subject: UserPreview
    question: QuestionPreview
    user: UserPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "question": question_link(self.question),
            "user": user_link(self.user),
        }


class InviteAnswerInternal(BaseModel):
    verb: Literal["invite_answer"] = "invite_answer"
    subject_id: int
    question_id: int
    user_id: int


class InviteNewUser(BaseModel):
    verb: Literal["invite_new_user"] = "invite_new_user"
    subject: UserPreview
    site: Optional[Site]
    invited_email: Optional[CaseInsensitiveEmailStr] = None

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "site": map_(self.site, site_link),
            "invited_email": self.invited_email,
        }


class InviteNewUserInternal(BaseModel):
    verb: Literal["invite_new_user"] = "invite_new_user"
    subject_id: int
    site_id: Optional[int]
    invited_email: Optional[CaseInsensitiveEmailStr] = None


class InviteJoinSite(BaseModel):
    verb: Literal["invite_join_site"] = "invite_join_site"
    subject: UserPreview
    site: Optional[
        Site
    ]  # TODO: Must be not-null. Delete non-conformant data after a while.
    user: Optional[UserPreview]
    invited_email: Optional[
        CaseInsensitiveEmailStr
    ] = None  # Deprecated, see `InviteNewUser`

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "site": map_(self.site, site_link),
            "user": map_(self.user, user_link),
            "invited_email": self.invited_email,
        }


class InviteJoinSiteInternal(BaseModel):
    verb: Literal["invite_join_site"] = "invite_join_site"
    subject_id: int
    site_id: Optional[
        int
    ]  # TODO: Must be not-null. Delete non-conformant data after a while.
    user_id: Optional[int]
    invited_email: Optional[
        CaseInsensitiveEmailStr
    ] = None  # Deprecated, see `InviteNewUser`


class SystemSendInvitation(BaseModel):
    verb: Literal["system_send_invitation"] = "system_send_invitation"
    invited_email: CaseInsensitiveEmailStr

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "invited_email": self.invited_email,
        }


class InvitedUserActivated(BaseModel):
    verb: Literal["invited_user_activated"] = "invited_user_activated"
    invited_email: CaseInsensitiveEmailStr
    payment_amount: Optional[int]

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "invited_email": self.invited_email,
            "payment_amount": str(self.payment_amount),
        }


class ApplyJoinSite(BaseModel):
    verb: Literal["apply_join_site"] = "apply_join_site"
    subject: UserPreview
    site: Site

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "site": site_link(self.site),
        }


class ApplyJoinSiteInternal(BaseModel):
    verb: Literal["apply_join_site"] = "apply_join_site"
    subject_id: int
    site_id: int


class CommentAnswer(BaseModel):
    verb: Literal["comment_answer"] = "comment_answer"
    subject: UserPreview
    comment: Comment
    answer: AnswerPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "comment": comment_short_or_link(self.comment),
            "answer": answer_link(self.answer),
            "question": question_link(self.answer.question),
        }


class CommentAnswerInternal(BaseModel):
    verb: Literal["comment_answer"] = "comment_answer"
    subject_id: int
    comment_id: int
    answer_id: int


class UpvoteAnswer(BaseModel):
    verb: Literal["upvote_answer"] = "upvote_answer"
    subject: UserPreview
    answer: AnswerPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "answer": answer_link(self.answer),
            "question": question_link(self.answer.question),
        }


class UpvoteAnswerInternal(BaseModel):
    verb: Literal["upvote_answer"] = "upvote_answer"
    subject_id: int
    answer_id: int


class UpvoteArticle(BaseModel):
    verb: Literal["upvote_article"] = "upvote_article"
    subject: UserPreview
    article: ArticlePreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "article": article_link(self.article),
        }


class UpvoteArticleInternal(BaseModel):
    verb: Literal["upvote_article"] = "upvote_article"
    subject_id: int
    article_id: int


class UpvoteQuestion(BaseModel):
    verb: Literal["upvote_question"] = "upvote_question"
    subject: UserPreview
    question: QuestionPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "question": question_link(self.question),
        }


class UpvoteQuestionInternal(BaseModel):
    verb: Literal["upvote_question"] = "upvote_question"
    subject_id: int
    question_id: int


class CreateSiteInternal(BaseModel):
    verb: Literal["create_site"] = "create_site"
    subject_id: int
    site_id: int


class CreateSite(BaseModel):
    verb: Literal["create_site"] = "create_site"
    subject: UserPreview
    site: Site

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "site": map_(self.site, site_link),
        }


class CreateSiteNeedApprovalInternal(BaseModel):
    verb: Literal["create_site_need_approval"] = "create_site_need_approval"
    subject_id: int
    channel_id: int


class CreateSiteNeedApproval(BaseModel):
    verb: Literal["create_site_need_approval"] = "create_site_need_approval"
    subject: UserPreview
    channel: Channel

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "channel": map_(self.channel, channel_link),
        }


class UpvoteSubmission(BaseModel):
    verb: Literal["upvote_submission"] = "upvote_submission"
    subject: UserPreview
    submission: Submission

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "submission": submission_link(self.submission),
        }


class UpvoteSubmissionInternal(BaseModel):
    verb: Literal["upvote_submission"] = "upvote_submission"
    subject_id: int
    submission_id: int


class FollowUser(BaseModel):
    verb: Literal["follow_user"] = "follow_user"
    subject: UserPreview
    user: UserPreview

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "user": user_link(self.user),
        }


class FollowUserInternal(BaseModel):
    verb: Literal["follow_user"] = "follow_user"
    subject_id: int
    user_id: int


class SubscribeArticleColumn(BaseModel):
    verb: Literal["follow_article_column"] = "follow_article_column"
    subject: UserPreview
    article_column: ArticleColumn

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "article_column": article_column_link(self.article_column),
        }


class SubscribeArticleColumnInternal(BaseModel):
    verb: Literal["follow_article_column"] = "follow_article_column"
    subject_id: int
    article_column_id: int


class SystemBroadcast(BaseModel):
    verb: Literal["system_broadcast"] = "system_broadcast"
    message: str

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "message": self.message,
        }


class SiteBroadcastInternal(BaseModel):
    verb: Literal["site_broadcast"] = "site_broadcast"
    submission_id: int
    site_id: int


class SiteBroadcast(BaseModel):
    verb: Literal["site_broadcast"] = "site_broadcast"
    submission: Submission
    site: Site

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "submission": submission_link(self.submission),
            "site": map_(self.site, site_link),
        }


class CreateMessage(BaseModel):
    verb: Literal["create_message"] = "create_message"
    subject: UserPreview
    channel: Channel

    def _string_args(self) -> Mapping[str, StringArg]:
        return {
            "who": user_link(self.subject),
            "channel": channel_link(self.channel),
        }


class CreateMessageInternal(BaseModel):
    verb: Literal["create_message"] = "create_message"
    subject_id: int
    channel_id: int


class Event(BaseModel):
    created_at: datetime.datetime
    content: Union[
        CreateQuestion,
        AnswerQuestion,
        CommentQuestion,
        ReplyComment,
        InviteAnswer,
        InviteNewUser,
        InviteJoinSite,
        ApplyJoinSite,
        CommentAnswer,
        UpvoteAnswer,
        UpvoteQuestion,
        FollowUser,
        SystemBroadcast,
        CreateMessage,
        SystemSendInvitation,
        InvitedUserActivated,
        CreateArticle,
        CommentArticle,
        UpvoteArticle,
        SubscribeArticleColumn,
        AnswerUpdate,
        CreateAnswerQuestionReward,
        ClaimAnswerQuestionReward,
        CreateSubmission,
        UpvoteSubmission,
        CommentSubmission,
        SiteBroadcast,
        EditQuestion,
        MentionedInComment,
        CreateSite,
        CreateSubmissionSuggestion,
        AcceptSubmissionSuggestion,
        CreateSiteNeedApproval,
        CreateAnswerSuggestEdit,
        AcceptAnswerSuggestEdit,
    ]


class EventInternal(BaseModel):
    created_at: datetime.datetime
    content: Union[
        CreateQuestionInternal,
        AnswerQuestionInternal,
        CommentQuestionInternal,
        CommentSubmissionInternal,
        ReplyCommentInternal,
        InviteAnswerInternal,
        InviteNewUserInternal,
        InviteJoinSiteInternal,
        ApplyJoinSiteInternal,
        CommentAnswerInternal,
        UpvoteAnswerInternal,
        UpvoteQuestionInternal,
        FollowUserInternal,
        SystemBroadcast,
        CreateMessageInternal,
        SystemSendInvitation,
        InvitedUserActivated,
        CreateArticleInternal,
        CommentArticleInternal,
        UpvoteArticleInternal,
        SubscribeArticleColumnInternal,
        AnswerUpdateInternal,
        CreateAnswerQuestionRewardInternal,
        ClaimAnswerQuestionRewardInternal,
        CreateSubmissionInternal,
        UpvoteSubmissionInternal,
        CommentSubmissionInternal,
        SiteBroadcastInternal,
        EditQuestionInternal,
        MentionedInCommentInternal,
        CreateSiteInternal,
        CreateSubmissionSuggestionInternal,
        AcceptSubmissionSuggestionInternal,
        CreateSiteNeedApprovalInternal,
        CreateAnswerSuggestEditInternal,
        AcceptAnswerSuggestEditInternal,
    ]
