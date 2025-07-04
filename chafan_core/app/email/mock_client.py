from email.message import EmailMessage
from email.generator import Generator

class MockEmailClient(object):
    smtp = None
    def __init__(self):
        pass
    def build_email(self, from_addr, to_addrs, subject, text)->EmailMessage:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_addrs # TODO not tested if it supports more emails 2025-06-25
        msg.set_content(text)
        return msg
    def login(self):
        self.smtp = "Mock_Smtp"
    def quit(self):
        self.smtp = None


    def send_email(self, from_addr, to_addr, subject, text):
        print("Dry-run: send email")
        if self.smtp is None:
            raise ValueError("smtp client is not initialized")
