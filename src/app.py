import os
from dotenv import load_dotenv
load_dotenv()

import sqlite3
from flask import Flask
from flask_wtf.csrf import CSRFProtect

from blueprints import home
from database import create_signup_schema

app = Flask(__name__)
app.debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')

app.register_blueprint(home)

os.makedirs(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts'), exist_ok=True)

secret_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts', '.secret')
if os.path.exists(secret_file):
    with open(secret_file, 'rb') as f:
        secret_key = f.read()
else:
    secret_key = os.urandom(32)
    with open(secret_file, 'wb') as f:
        f.write(secret_key)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secret_key)
app.config['ENABLE_DISCORD'] = os.environ.get('ENABLE_DISCORD', 'False').lower() in ('true', '1')
app.config['ENABLE_EMAIL'] = os.environ.get('ENABLE_EMAIL', 'True').lower() in ('true', '1')
app.config['DISCORD_WEBHOOK_URL'] = os.environ.get('DISCORD_WEBHOOK_URL')
app.config['GMAIL_SENDER_EMAIL'] = os.environ.get('GMAIL_SENDER_EMAIL')
app.config['GMAIL_APP_PASSWORD'] = os.environ.get('GMAIL_APP_PASSWORD')

csrf = CSRFProtect(app)

db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts', 'database.db')
connection = sqlite3.connect(db_path)

import time
db_retries = 3
while db_retries > 0:
    try:
        connection.execute("SELECT * FROM signups;")
        create_signup_schema(connection)
        break
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower() or 'busy' in str(e).lower():
            time.sleep(0.5)
            db_retries -= 1
        else:
            create_signup_schema(connection)
            break

connection.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
