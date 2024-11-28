import smtplib
from email.message import EmailMessage
from ..mycelery import send_HTML_mail_task, send_text_mail_task

class SMTPSender():
    _server: str
    _port: int
    _email: str
    _password: str

    def __init__(self, server: str, port: int, email: str, password: str):
        self._email = str(email)
        self._password = str(password)
        self._server = str(server)
        self._port = int(port)

    def send_text_mail(self, to_email: str, subject: str, text_message: str):
        with smtplib.SMTP(self._server, self._port) as mail_server:
            mail_server.ehlo()
            mail_server.starttls()
            mail_server.ehlo()
            mail_server.login(self._email, self._password)

            mail_server.sendmail(self._email, to_email, f"Subject: {subject}\n\n{text_message}".encode('utf-8'))
    
    def send_HTML_mail(self, to_email: str, subject: str, html: str):
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self._email
        msg['To'] = to_email
        msg.add_header('Content-Type','text/html')
        msg.set_payload(html)

        with smtplib.SMTP(self._server, self._port) as mail_server:
            mail_server.ehlo()
            mail_server.starttls()
            mail_server.ehlo()
            mail_server.login(self._email, self._password)

            mail_server.sendmail(self._email, to_email, msg.as_string().encode('utf-8'))
    
    def send_text_mail_task(self, to_email: str, subject: str, text_message: str):
        send_text_mail_task.delay(self._server, self._port, self._email, self._password, to_email, subject, text_message)
    
    def send_HTML_mail_task(self, to_email: str, subject: str, html: str):
        send_HTML_mail_task.delay(self._server, self._port, self._email, self._password, to_email, subject, html)