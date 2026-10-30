import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage

DISCORD_TIMEOUT = 3
SMTP_TIMEOUT = 8


def send_discord(text):
    url = (os.environ.get('DISCORD_WEBHOOK_URL') or '').strip()
    if not url or not text:
        return False
    body = json.dumps({
        'content': text[:1900],
        'allowed_mentions': {'parse': []},
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'opendecks',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=DISCORD_TIMEOUT) as response:
            response.read()
        return True
    except Exception as exc:
        print('discord notify failed:', type(exc).__name__)
        return False


def _mail_address(value):
    address = (value or '').strip()
    if not address or '@' not in address or any(ch in address for ch in '\r\n'):
        return None
    return address


def gmail_account():
    sender = _mail_address(os.environ.get('GMAIL_SENDER_EMAIL'))
    login = _mail_address(os.environ.get('GMAIL_SMTP_USER')) or sender
    password = ''.join((os.environ.get('GMAIL_APP_PASSWORD') or '').split())
    if not sender or not login or not password:
        return None
    return login, sender, password


def mail_configured():
    return gmail_account() is not None


def send_email(to, subject, body):
    account = gmail_account()
    if not account or not to or not subject or not body:
        return False
    if any(ch in to or ch in subject for ch in '\r\n'):
        return False
    login, sender, password = account
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f'open decks <{sender}>'
    msg['To'] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=SMTP_TIMEOUT) as smtp:
            smtp.login(login, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print('email failed! FUCKING BITCH ASS, WHY ON EARTH YOU NOT WORKING??? SHIT!', type(exc).__name__)
        return False
