from flask import Blueprint, render_template, request
from wtforms import Form, SubmitField, TextAreaField, validators


from database import insert_to_email_schema

home = Blueprint('home', __name__)


class EmailForm(Form):
    email = TextAreaField('ur instagram', validators=[
        validators.InputRequired(message="??"), 
        validators.Length(min=2, message="too short!"), 
        validators.Length(max=30, message="too long!")],
        render_kw={'rows': 1, 'cols': 25, 'style':'resize:none;background: black;color:white;font-family:Cambria, Cochin, Georgia, Times, "Times New Roman", serif;', 'placeholder': '@your_instagram_handle'})
    submit = SubmitField('subscribe', render_kw={'style':"border:none; background: lightgrey;"})

@home.route('/', methods=('GET', 'POST'))
def index():
    form = EmailForm(request.form)
    
    if request.method == 'POST' and form.validate():
        insert_to_email_schema(form.email.data)
        return render_template('success.html')      
        
    return render_template('index.html', form=form)
