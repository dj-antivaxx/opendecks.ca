import os

import sqlite3
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from blueprints import home
from database import create_email_schema

if __name__ == '__main__':
    app = Flask(__name__)
    app.debug = True

    app.register_blueprint(home)

    os.makedirs('./artifacts', exist_ok=True)

    database_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.join('..', './artifacts/db.sqlite'))
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database_path
    app.config['SECRET_KEY'] = 'secret-key-goes-here'

    connection = sqlite3.connect('./artifacts/database.db')

    try:
        connection.execute("SELECT * FROM EMAILZ;")
    except sqlite3.OperationalError:
        create_email_schema(connection)
    
    db = SQLAlchemy()
    db.init_app(app)
    with app.app_context():
        db.create_all()
    
    connection.close
   
    app.run(host='0.0.0.0')
