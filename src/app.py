import os
import sqlite3
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from blueprints import home
from database import create_signup_schema

app = Flask(__name__)
app.debug = True

app.register_blueprint(home)

os.makedirs('./artifacts', exist_ok=True)

database_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.join('..', './artifacts/db.sqlite'))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database_path
app.config['SECRET_KEY'] = 'secret-key-goes-here'

csrf = CSRFProtect(app)

connection = sqlite3.connect('./artifacts/database.db')

try:
    connection.execute("SELECT * FROM signups;")
except sqlite3.OperationalError:
    create_signup_schema(connection)

db = SQLAlchemy()
db.init_app(app)
with app.app_context():
    db.create_all()

connection.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='8880')
