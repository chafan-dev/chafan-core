from typing import Dict, Any

from chafan_core.app.config import settings
from chafan_core.app.email.smtp_client import SmtpClient
from chafan_core.app.email.mock_client import MockEmailClient

import logging
logger = logging.getLogger(__name__)


async def send_reset_password_email(email: str, token: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - 密码重置 {email}"
    #with open(Path(settings.EMAIL_TEMPLATES_DIR) / "reset_password.html") as f:
    #    template_str = f.read()
    #server_host = str(settings.SERVER_HOST).strip("/")
    #link = f"{server_host}/reset-password?token={token}"
    logger.info(f"Send reset password email to {email}")
    await send_email(
        email_to=email,
        subject=subject,
        html_body="您好！\n感谢您的支持！该功能在紧急开发中 " + token[:20],
        #html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": "a"#link,
        },
    )

async def send_email(
    email_to: str,
    subject: str = "",
    html_body: str = "",
    environment: Dict[str, Any] = {},
    ):
    if settings.EMAILS_ENABLED:
        client = SmtpClient()
    else:
        logger.warn(f"Dry-run send email to {email_to}, subject {subject}")
        client = MockEmailClient()
    client.login()
    client.send_email("admin@cha.fan", email_to, subject, html_body)
    client.quit()

