# selfnote 2025-06-25 everything about email should be hidden behind this file

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode

from chafan_core.app import schemas
from chafan_core.app.common import from_now, is_dev, render_notif_content
from chafan_core.app.config import settings

# from emails.template import JinjaTemplate  # type: ignore


# TODO this file should be moved into chafan_core/app/email_util


# Old code
def send_email(
    email_to: str,
    subject_template: str = "",
    html_template: str = "",
    environment: Dict[str, Any] = {},
) -> None:
    return


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
    host = settings.API_SERVER_SCHEME + "://" + settings.SERVER_HOST
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


def send_verification_code_phone_number(_phone_number: str, _code: str) -> None:
    raise NotImplementedError("No longer support SMS")


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
