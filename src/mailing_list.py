import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from flask import render_template_string

def send_welcome_email(name, receiver_email):
    load_dotenv()
    
    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    
    if not sender_email or not app_password:
        raise ValueError("GMAIL_SENDER_EMAIL or GMAIL_APP_PASSWORD is not set in environment variables, my ass.")

    template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates', 'welcome_email.html')
    with open(template_path, 'r') as f:
        html_content = render_template_string(f.read(), name=name)

    msg = EmailMessage()
    msg['Subject'] = 'We got chu Fam!!! 10 year anniversary fundraiser for n10.as'
    msg['From'] = f"DJ Antivaxx <{sender_email}>"
    msg['To'] = receiver_email
    
    msg.set_content(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, app_password)
            smtp.send_message(msg)
            print(f"Welcome email ABSOLUTELY GRACEFULLY sent to {receiver_email}!")
    except Exception as e:
        print(f"Unfortunately, we did not succeed sending the fucking email to {receiver_email}. Exception: {e}")
        raise e
