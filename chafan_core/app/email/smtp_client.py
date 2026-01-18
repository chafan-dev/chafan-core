import logging
import smtplib
import ssl

from chafan_core.app.config import settings
from chafan_core.app.email.mock_client import MockEmailClient

logger = logging.getLogger(__name__)


class SmtpClient(MockEmailClient):
    smtp = None
    host = None
    port = None
    username = None
    password = None
    debug = False

    def login(self):
        server = smtplib.SMTP(self.host, self.port, timeout=30)
        if self.debug:
            server.set_debuglevel(2)
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(self.username, self.password)
        server.ehlo()
        self.smtp = server

    def __init__(self, debug=False):
        self.host = settings.EMAIL_SMTP_HOST
        self.port = settings.EMAIL_SMTP_PORT
        self.username = settings.EMAIL_SMTP_LOGIN_USERNAME
        self.password = settings.EMAIL_SMTP_LOGIN_PASSWORD
        self.debug = debug
        if self.host is None or self.host == "":
            raise ValueError("EMAIL_SMTP_HOST not defined")
        if self.port is None:
            raise ValueError("EMAIL_SMTP_HOST not defined")
        logger.info(f"Create SMTP to host {self.host} : {self.port}")

    def send_email(self, from_addr, to_addr, subject, text):
        if self.smtp is None:
            raise ValueError("smtp client is not initialized")
        msg = self.build_email(from_addr, to_addr, subject, text)
        self.smtp.sendmail(from_addr, to_addr, msg.as_bytes())

    def quit(self):
        if self.smtp is None:
            return
        self.smtp.quit()
        self.smtp = None
