import html2text
import sentry_sdk
from botocore.exceptions import ClientError

from chafan_core.app.aws import get_ses_client
from chafan_core.app.common import is_dev
from chafan_core.app.config import settings


def send_email_ses(email_to: str, body_html: str, subject: str) -> None:
    if is_dev():
        return
    try:
        ses = get_ses_client()
        ses.send_email(
            Destination={
                "ToAddresses": [
                    email_to,
                ],
            },
            Message={
                "Body": {
                    "Html": {
                        "Charset": "utf-8",
                        "Data": body_html,
                    },
                    "Text": {
                        "Charset": "utf-8",
                        "Data": html2text.html2text(body_html),
                    },
                },
                "Subject": {
                    "Charset": "utf-8",
                    "Data": subject,
                },
            },
            Source=settings.EMAILS_FROM_EMAIL,
        )
    except ClientError as e:
        sentry_sdk.capture_exception(e)
