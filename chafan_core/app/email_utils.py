import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode

#from emails.template import JinjaTemplate  # type: ignore

from chafan_core.app import schemas
from chafan_core.app.aws_ses import send_email_ses
from chafan_core.app.aws_sns import send_sms
from chafan_core.app.common import from_now, is_dev, render_notif_content
from chafan_core.app.config import settings


def send_email(
    email_to: str,
    subject_template: str = "",
    html_template: str = "",
    environment: Dict[str, Any] = {},
) -> None:
    assert settings.EMAILS_ENABLED, "no provided configuration for email variables"
    body_html = html_template
    #body_html = JinjaTemplate(html_template).render(**environment)
    if is_dev():
        mailbox_dir = f"/tmp/chafan/mailbox/{email_to}/"
        os.makedirs(mailbox_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=mailbox_dir, delete=False, suffix=".html"
        ) as tmp:
            tmp.write(body_html)
    else:
        send_email_ses(
            email_to=email_to,
            subject=JinjaTemplate(subject_template).render(**environment),
            body_html=body_html,
        )


def send_reset_password_email(email: str, token: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - 密码重置 {email}"
    with open(Path(settings.EMAIL_TEMPLATES_DIR) / "reset_password.html") as f:
        template_str = f.read()
    server_host = str(settings.SERVER_HOST).strip("/")
    link = f"{server_host}/reset-password?token={token}"
    send_email(
        email_to=email,
        subject_template=subject,
        html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )


def send_feedback_status_update_email(email: str, desc: str, new_status: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - 您的反馈状态有更新"
    with open(Path(settings.EMAIL_TEMPLATES_DIR) / "feedback_status_update.html") as f:
        template_str = f.read()
    send_email(
        email_to=email,
        subject_template=subject,
        html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "desc": desc,
            "new_status": new_status,
        },
    )


def send_notification_email(
    email: str,
    notifications: List[schemas.Notification],
    unsubscribe_token: str,
) -> None:
    project_name = settings.PROJECT_NAME
    with open(Path(settings.EMAIL_TEMPLATES_DIR) / "notifications.html") as f:
        template_str = f.read()
    notifications_repr = []
    first_title = None
    for notif in notifications:
        rendered = render_notif_content(notif)
        if rendered is None:
            continue
        if not first_title:
            first_title = rendered.headline
        notifications_repr.append(
            {
                "body": rendered.full,
                "created_at": from_now(notif.created_at, locale="zh"),
            }
        )
    subject = f"{project_name} 未读通知"
    if first_title:
        subject += f"：{first_title}..."
    host = settings.API_SERVER_SCHEME + "://" + settings.SERVER_NAME
    params = {
        "email": email,
        "type": "unread_notifications",
        "unsubscribe_token": unsubscribe_token,
    }
    unsubscribe_link = f"{host}/api/v1/unsubscribe?{urlencode(params)}"
    send_email(
        email_to=email,
        subject_template=subject,
        html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "notifications": notifications_repr,
            "unsubscribe_link": unsubscribe_link,
        },
    )


def send_verification_code_phone_number(phone_number: str, code: str) -> None:
    project_name = settings.PROJECT_NAME
    text = f"{project_name} - 验证码 {code} ({settings.PHONE_NUMBER_VERIFICATION_CODE_EXPIRE_HOURS} 小时内过期)"
    send_sms(phone_number, text)


def send_verification_code_email(email: str, code: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - 验证码 {code}"
    with open(Path(settings.EMAIL_TEMPLATES_DIR) / "verification_code.html") as f:
        template_str = f.read()
    server_host = str(settings.SERVER_HOST).strip("/")
    params = {"email": email, "code": code}
    link = f"{server_host}/signup?{urlencode(params)}"
    send_email(
        email_to=email,
        subject_template=subject,
        html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "email": email,
            "valid_hours": settings.EMAIL_SIGNUP_CODE_EXPIRE_HOURS,
            "code": code,
            "link": link,
        },
    )


def send_new_account_email(email_to: str, username: str, password: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    with open(Path(settings.EMAIL_TEMPLATES_DIR) / "new_account.html") as f:
        template_str = f.read()
    link = settings.SERVER_HOST
    send_email(
        email_to=email_to,
        subject_template=subject,
        html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": link,
        },
    )
