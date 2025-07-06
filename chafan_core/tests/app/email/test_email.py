import logging
logger = logging.getLogger(__name__)

from chafan_core.app.email.utils       import send_reset_password_email, apply_email_template
from chafan_core.app.email.mock_client import MockEmailClient
from chafan_core.app.config import settings

import pytest
import jinja2

def test_apply_email_template():
    result = apply_email_template("reset_password", {}, allow_undefined=True)
    assert isinstance(result, str)
    assert len(result)>100
    with pytest.raises(jinja2.exceptions.UndefinedError) as exec_info:
        _ = apply_email_template("reset_password", {})
    assert "undefined" in str(exec_info.value)


def test_client():
    client = MockEmailClient()
    client.login()
    client.send_email("stub@cha.fan", "stub_receiver@cha.fan", "subject", "test mail")
    client.quit()

async def test_send_reset_password_email():
    settings.EMAILS_ENABLED = False
    await send_reset_password_email("test@cha.fan", "stub_token")


