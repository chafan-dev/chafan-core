"""Small resource schemas (message, form, profile, channel, …).

Free functions take a Materializer-like object (preview_of_user, principal,
broker/get_db) so Materializer methods can thin-delegate here.
"""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic.tools import parse_obj_as

from chafan_core.app import models, schemas
from chafan_core.utils.base import map_


def message_schema_from_orm(mat, message: models.Message) -> schemas.Message:
    base = schemas.MessageInDBBase.from_orm(message)
    d = base.dict()
    d["author"] = mat.preview_of_user(message.author)
    return schemas.Message(**d)


def form_schema_from_orm(mat, form: models.Form) -> schemas.Form:
    base = schemas.FormInDBBase.from_orm(form)
    d = base.dict()
    d["author"] = mat.preview_of_user(form.author)
    return schemas.Form(**d)


def form_response_schema_from_orm(
    mat, form_response: models.FormResponse
) -> schemas.FormResponse:
    base = schemas.FormResponseInDBBase.from_orm(form_response)
    d = base.dict()
    d["response_author"] = mat.preview_of_user(form_response.response_author)
    d["form"] = form_schema_from_orm(mat, form_response.form)
    return schemas.FormResponse(**d)


def webhook_schema_from_orm(mat, webhook: models.Webhook) -> schemas.Webhook:
    base = schemas.WebhookInDB.from_orm(webhook)
    d = base.dict()
    d["site"] = mat.site_schema_from_orm(webhook.site)
    return schemas.Webhook(**d)


def profile_schema_from_orm(mat, profile: models.Profile) -> schemas.Profile:
    base = schemas.ProfileInDBBase.from_orm(profile)
    d = base.dict()
    d["site"] = mat.site_schema_from_orm(profile.site)
    d["owner"] = mat.preview_of_user(profile.owner)
    return schemas.Profile(**d)


def feedback_schema_from_orm(mat, f: models.Feedback) -> schemas.Feedback:
    ret = schemas.Feedback(
        id=f.id,
        created_at=f.created_at,
        description=f.description,
        status=f.status,
        has_screenshot=f.screenshot_blob is not None,
    )
    if f.user:
        ret.user = mat.preview_of_user(f.user)
    elif f.user_email:
        ret.user_email = f.user_email
    return ret


def channel_schema_from_orm(mat, channel: models.Channel) -> schemas.Channel:
    base = schemas.ChannelInDBBase.from_orm(channel)
    d = base.dict()
    if channel.private_with_user:
        d["private_with_user"] = mat.preview_of_user(channel.private_with_user)
    d["admin"] = mat.preview_of_user(channel.admin)
    if channel.feedback_subject:
        d["feedback_subject"] = feedback_schema_from_orm(mat, channel.feedback_subject)
    return schemas.Channel(**d)


def report_schema_from_orm(mat, report: models.Report) -> schemas.Report:
    base = schemas.ReportInDBBase.from_orm(report)
    d = base.dict()
    d["author"] = mat.preview_of_user(report.author)
    return schemas.Report(**d)


def audit_log_schema_from_orm(mat, audit_log: models.AuditLog) -> schemas.AuditLog:
    base = schemas.AuditLogInDBBase.from_orm(audit_log)
    d = base.dict()
    d["user"] = mat.preview_of_user(audit_log.user)
    return schemas.AuditLog(**d)


def application_schema_from_orm(
    mat, application: models.Application
) -> schemas.Application:
    base = schemas.ApplicationInDBBase.from_orm(application)
    d = base.dict()
    d["applicant"] = mat.preview_of_user(application.applicant)
    d["applied_site"] = mat.site_schema_from_orm(application.applied_site)
    return schemas.Application(**d)


def reward_schema_from_orm(mat, reward: models.Reward) -> schemas.Reward:
    base = schemas.RewardInDBBase.from_orm(reward)
    d = base.dict()
    d["giver"] = mat.preview_of_user(reward.giver)
    d["receiver"] = mat.preview_of_user(reward.receiver)
    if reward.condition:
        d["condition"] = parse_obj_as(schemas.reward.RewardCondition, reward.condition)
    return schemas.Reward(**d)


def invitation_link_schema_from_orm(
    mat, invitation_link: models.InvitationLink
) -> schemas.InvitationLink:
    base = schemas.InvitationLinkInDB.from_orm(invitation_link)
    d = base.dict()
    d["invited_to_site"] = map_(
        invitation_link.invited_to_site, mat.site_schema_from_orm
    )
    d["inviter"] = mat.preview_of_user(invitation_link.inviter)
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    d["valid"] = (
        invitation_link.expired_at > utc_now and invitation_link.remaining_quota > 0
    )
    return schemas.InvitationLink(**d)


def get_user_article_column_subscription(
    mat, article_column: models.ArticleColumn
) -> schemas.UserArticleColumnSubscription:
    principal = getattr(mat, "principal", None)
    if principal is None and getattr(mat, "principal_id", None) is not None:
        # RequestContext path: resolve principal if needed
        try:
            principal = mat.try_get_current_user()
        except Exception:
            principal = None
    if principal:
        subscribed = article_column in principal.subscribed_article_columns
    else:
        subscribed = False
    return schemas.UserArticleColumnSubscription(
        article_column_uuid=article_column.uuid,
        subscription_count=article_column.subscribers.count(),
        subscribed_by_me=subscribed,
    )


def article_column_schema_from_orm(
    mat, article_column: models.ArticleColumn
) -> schemas.ArticleColumn:
    base = schemas.ArticleColumnInDBBase.from_orm(article_column)
    data_dict = base.dict()
    data_dict["owner"] = mat.preview_of_user(article_column.owner)
    data_dict["subscription"] = get_user_article_column_subscription(
        mat, article_column
    )
    return schemas.ArticleColumn(**data_dict)


def task_schema_from_orm(mat, task: models.Task) -> schemas.Task:
    base = schemas.TaskInDB.from_orm(task)
    d = base.dict()
    d["initiator"] = mat.preview_of_user(task.initiator)
    return schemas.Task(**d)
