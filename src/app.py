import os
import argparse
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

app.config['MAX_CONTENT_LENGTH'] = 5.5 * 1024 * 1024

secret_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts', '.secret')
if os.path.exists(secret_file):
    with open(secret_file, 'rb') as f:
        secret_key = f.read()
else:
    secret_key = os.urandom(32)
    with open(secret_file, 'wb') as f:
        f.write(secret_key)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secret_key)
app.config['DISABLE_DISCORD'] = os.environ.get('DISABLE_DISCORD', 'False').lower() in ('true', '1')
app.config['DISABLE_EMAIL'] = os.environ.get('DISABLE_EMAIL', 'False').lower() in ('true', '1')

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
    parser = argparse.ArgumentParser(description="opendecks.ca")
    parser.add_argument('--disable-discord', action='store_true', help="turn off yo discord webhook notifications")
    parser.add_argument('--disable-email', action='store_true', help="turn off yo email notifications")
    args = parser.parse_args()
    
    if args.disable_discord:
        app.config['DISABLE_DISCORD'] = True
    if args.disable_email:
        app.config['DISABLE_EMAIL'] = True

    app.run(host='0.0.0.0', port=5001)
