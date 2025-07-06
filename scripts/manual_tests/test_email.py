
def test_smtp():
    from chafan_core.app.config import settings

    from chafan_core.app.email.smtp_client import SmtpClient
    client = SmtpClient(debug=True)
    client.login()
    client.send_email("admin@cha.fan", "chai_inu@cha.fan", "test header", "greeting to self")
    client.quit()

test_smtp()
