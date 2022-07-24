from chafan_core.app.email_utils import send_verification_code_email

def test_send_verification_code_email(mocker):
    mocker.patch("chafan_core.app.config.settings.EMAILS_ENABLED", True)
    send_verification_code_email("test@example.com", "123456")
