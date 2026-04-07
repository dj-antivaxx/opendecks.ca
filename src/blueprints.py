import os
import requests
import concurrent.futures
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from wtforms import StringField, SubmitField, validators
from flask_wtf import FlaskForm
from database import insert_signup
from mailing_list import send_welcome_email

home = Blueprint('home', __name__)

executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

class SignUpForm(FlaskForm):
    email = StringField(
        '',
        validators=[
            validators.InputRequired(message="Email is required."),
            validators.Email(message="Invalid email address."),
            validators.Length(max=100)
        ],
        render_kw={'placeholder': 'email address', 'aria-label': 'Email address'}
    )
    submit = SubmitField('>')

def send_notifications_async(enable_discord, discord_webhook_url, discord_message, enable_email, sender, password, email_addr):
    if enable_discord and discord_webhook_url and discord_message:
        try:
            requests.post(discord_webhook_url, json=discord_message, timeout=10)
        except Exception as e:
            print(f"Error sending Discord notification: {e}")
            
    if enable_email and sender and password:
        try:
            send_welcome_email(email_addr, sender, password)
        except Exception as e:
            print(f"Error sending welcome email: {e}")


@home.route('/', methods=['GET', 'POST'])
def index():
    form = SignUpForm()
    if request.method == 'POST' and form.validate_on_submit():
        
        insert_signup(form.email.data)
        
        discord_message = {
            "content": f"\n**New submission:**\n"
                       f"**email:** {form.email.data}\n"
        }
        
        executor.submit(
            send_notifications_async,
            current_app.config.get('ENABLE_DISCORD', False),
            current_app.config.get('DISCORD_WEBHOOK_URL'),
            discord_message,
            current_app.config.get('ENABLE_EMAIL', True),
            current_app.config.get('GMAIL_SENDER_EMAIL'),
            current_app.config.get('GMAIL_APP_PASSWORD'),
            form.email.data
        )
            
        return redirect(url_for('home.thank_you'))
    return render_template('sign_up.html', form=form)


@home.route('/thank_you', methods=['GET'])
def thank_you():
    return render_template('thank_you.html')
