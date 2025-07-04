
from chafan_core.app.email.mock_client import MockEmailClient



def test_client():
    client = MockEmailClient()
    client.login()
    client.send_email("stub@cha.fan", "stub_receiver@cha.fan", "subject", "test mail")
    client.quit()

def test_smtp(capsys):
    from chafan_core.app.config import settings
    return

    from chafan_core.app.email.smtp_client import SmtpClient
    client = SmtpClient()
    client.send_email("admin@cha.fan", "chai_inu@cha.fan", "test mail")


