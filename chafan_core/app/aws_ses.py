import html2text
import sentry_sdk
from botocore.exceptions import ClientError

from chafan_core.app.aws import get_ses_client
from chafan_core.app.common import is_dev
from chafan_core.app.config import settings

# TODO This API should be removed # 2025-Jul-04
def send_email_ses(email_to: str, body_html: str, subject: str) -> None:
    if is_dev():
        return
