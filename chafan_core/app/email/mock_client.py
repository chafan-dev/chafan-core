from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class MockEmailClient(object):
    smtp = None

    def __init__(self):
        pass

    def build_email(self, from_addr, to_addrs, subject, html_body) -> EmailMessage:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addrs  # TODO not tested if it supports more emails 2025-06-25
        part1 = MIMEText("Thanks for using cha.fan", "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)
        return msg

    def login(self):
        self.smtp = "Mock_Smtp"

    def quit(self):
        self.smtp = None

    def send_email(self, from_addr, to_addr, subject, text):
        print("Dry-run: send email")
        if self.smtp is None:
            raise ValueError("smtp client is not initialized")
