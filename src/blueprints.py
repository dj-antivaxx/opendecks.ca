from flask import Blueprint, render_template, request, redirect, url_for
from wtforms import StringField, SubmitField, BooleanField, validators
from flask_wtf import FlaskForm
from database import insert_signup

home = Blueprint('home', __name__)


@home.route('/', methods=('GET', 'POST'))
def index():
    return render_template('index.html', show_signups=False)


class SignUpForm(FlaskForm):
    name = StringField(
        'DJ Name',
        validators=[
            validators.InputRequired(message="Name is required."),
            validators.Length(min=2, max=50, message="Name must be between 2 and 50 characters.")
        ],
        render_kw={
            'style': 'font-size: 1vh; margin-top: 1vh; background: black; color: white; font-family: Cambria, Cochin, Georgia, Times, "Times New Roman", serif;',
            'placeholder': 'Your Name'
        }
    )
    email = StringField(
        'Email',
        validators=[
            validators.InputRequired(message="Email is required."),
            # validators.Email(message="Invalid email address."),
            validators.Length(max=100, message="Email must be less than 100 characters.")
        ],
        render_kw={
            'style': 'font-size: 1vh; margin-top: 1vh; background: black; color: white; font-family: Cambria, Cochin, Georgia, Times, "Times New Roman", serif;',
            'placeholder': 'Your Email Address'
        }
    )

    agree = BooleanField(
        'I agree with terms and conditions',
        validators=[validators.InputRequired(message="You must agree to the terms and conditions.")],
        render_kw={
            'style': 'font-size: 1vh; margin-top: 1vh;'
        }
    )
    submit = SubmitField(
        'Sign Up',
        render_kw={
            'style': 'border: none; background: lightgrey; font-size: 1vh; margin-top: 2vh; cursor: pointer;'
        }
    )


@home.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    form = SignUpForm()
    if request.method == 'POST' and form.validate_on_submit():
        insert_signup(
            name=form.name.data,
            email=form.email.data,
            agree=form.agree.data
        )
        return redirect(url_for('home.thank_you'))
    return render_template('sign_up.html', form=form)


@home.route('/thank_you', methods=['GET'])
def thank_you():
    return render_template('thank_you.html')


@home.route('/tournament_info', methods=['GET'])
def tournament_info():
    return render_template('tournament_info.html')


@home.route('/past_events', methods=['GET'])
def past_events():
    event = request.args.get('event')
    return render_template('past_events.html', event=event)


@home.route('/terms_and_conditions', methods=['GET'])
def terms_and_conditions():
    return render_template('terms_and_conditions.html')
