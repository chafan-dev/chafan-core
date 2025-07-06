from typing import Dict, Any

from jinja2 import Template,StrictUndefined


from chafan_core.app.config import settings
from chafan_core.app.email.smtp_client import SmtpClient
from chafan_core.app.email.mock_client import MockEmailClient

import logging
logger = logging.getLogger(__name__)



def apply_email_template(template_name:str,
                         environment: Dict[str, Any] = {},
                         allow_undefined:bool = False) -> str:
    html_template_path = "{}/{}.html".format(settings.EMAIL_TEMPLATES_DIR, template_name)
    with open(html_template_path) as f:
        template_str = f.read()
    if allow_undefined:
        jinja = Template(template_str)
    else:
        jinja = Template(template_str,undefined=StrictUndefined)
    return jinja.render(environment)

async def send_reset_password_email(email: str, token: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - 密码重置 {email}"
    server_host = str(settings.SERVER_HOST).strip("/")
    link = f"{server_host}/reset-password?token={token}"
    environment={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
    }
    html_body = apply_email_template("reset_password", environment)
    logger.info(f"Send reset password email to {email}")
    await send_email(
        email_to=email,
        subject=subject,
        html_body=html_body,
    )

async def send_email(
    email_to: str,
    subject: str = "",
    html_body: str = "",
    ):
    # TODO I should move it out of send_email, but use dependency injection. 2025-Jul-04
    if settings.EMAILS_ENABLED:
        client = SmtpClient()
    else:
        logger.warning(f"Dry-run send email to {email_to}, subject {subject}")
        client = MockEmailClient()
    client.login()
    client.send_email("admin@cha.fan", email_to, subject, html_body)
    client.quit()

