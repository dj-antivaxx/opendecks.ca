import os
import uuid
import requests
import threading
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from wtforms import StringField, SubmitField, TextAreaField, validators, ValidationError
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired, FileSize
from werkzeug.utils import secure_filename
from database import insert_signup
from mailing_list import send_welcome_email
import re

home = Blueprint('home', __name__)

class SignUpForm(FlaskForm):
    name = StringField(
        'Your name',
        validators=[
            validators.InputRequired(message="Name is required, my friend."),
            validators.Length(min=2, max=50, message="We only accept names between 2 and 50 characters.")
        ],
        render_kw={'placeholder': 'DJ Foreskin'}
    )
    email = StringField(
        'Email (we will need it for confirmation)',
        validators=[
            validators.InputRequired(message="Email is required."),
            validators.Email(message="Ooops! Invalid email address."),
            validators.Length(max=100, message="Email is too long. This is not right.")
        ],
        render_kw={'placeholder': 'dj.antivaxx@gmail.com'}
    )
    
    n10as_message = TextAreaField(
        'Your Message',
        validators=[
            validators.Optional(),
            validators.Length(max=300, message="Please keep the message under 300 characters.")
        ],
        render_kw={
            'placeholder': "ask us anything (what's DJ Foreskin's favourite cheese?) or shoutout to DJ Antivaxx's mama. Please be polite because the message will be aired LIVE!",
            'rows': 4
        }
    )

    mp3_file = FileField(
        'Upload recording (5 minutes max)',
        validators=[
            FileAllowed(['mp3', 'webm', 'ogg', 'wav', 'm4a'], 'Audio files only (MP3, WebM, OGG, WAV, M4A)!'),
            FileSize(max_size=5 * 1024 * 1024, message="File must be less than 5MB bro wtf.")
        ]
    )
    submit = SubmitField('Submit')

    def validate_name(self, field):
        if not re.match(r'^[\w\s-]+$', field.data):
            raise ValidationError("What's wrong with your name! Letters and numbers only!")

def send_notifications_async(disable_discord, discord_webhook_url, discord_message, disable_email, name, email_addr):
    if not disable_discord and discord_webhook_url and discord_message:
        try:
            requests.post(discord_webhook_url, json=discord_message, timeout=10)
        except Exception as e:
            print(f"FUCK! Error sending Discord notification: {e}")
            
    if not disable_email:
        try:
            send_welcome_email(name, email_addr)
        except Exception as e:
            print(f"We got some bullshit error sending welcome email: {e}")


@home.route('/', methods=['GET', 'POST'])
def index():
    form = SignUpForm()
    if request.method == 'POST' and form.validate_on_submit():
        
        filename = None
        if form.mp3_file.data:
            f = form.mp3_file.data
            base_filename = secure_filename(f.filename)
            if not base_filename:
                base_filename = "upload"
            
            name_part, ext_part = os.path.splitext(base_filename)
            filename = f"{name_part}_{uuid.uuid4().hex[:8]}{ext_part}"
            
            upload_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            f.save(os.path.join(upload_folder, filename))
            
        insert_signup(
            name=form.name.data,
            email=form.email.data,
            n10as_message=form.n10as_message.data,
            mp3_filename=filename
        )
        
        disable_discord = current_app.config.get('DISABLE_DISCORD', False)
        discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
        disable_email = current_app.config.get('DISABLE_EMAIL', False)
        
        discord_message = None
        if not disable_discord and discord_webhook_url:
            discord_message = {
                "content": f"\n**wassup gang we got another one:**\n"
                           f"**name:** {form.name.data}\n"
                           f"**mailbox:** {form.email.data}\n"
                           f"**shout outs:** {form.n10as_message.data or 'nah'}\n"
                           f"**goodies:** {filename or 'nah'}"
            }
        
        thread = threading.Thread(target=send_notifications_async, args=(
            disable_discord, discord_webhook_url, discord_message, 
            disable_email, form.name.data, form.email.data
        ))
        thread.start()
            
        return redirect(url_for('home.thank_you', name=form.name.data))
    return render_template('sign_up.html', form=form)


@home.route('/thank_you', methods=['GET'])
def thank_you():
    name = request.args.get('name', 'fam')
    return render_template('thank_you.html', name=name)
