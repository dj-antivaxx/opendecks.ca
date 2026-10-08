import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request
from flask_wtf.csrf import CSRFProtect

from blueprints import home
from content import iso_day, long_date
from database import init_schema
from runtime import artifacts_dir, on_vercel

app = Flask(__name__)
app.debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')

app.register_blueprint(home)

is_vercel = on_vercel()

if is_vercel:
    missing = [
        name for name in ('SECRET_KEY', 'DATABASE_URL', 'BLOB_READ_WRITE_TOKEN')
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError('FUCK! refusing to start on Vercel without: ' + ', '.join(missing))
    secret_key = os.environ['SECRET_KEY']
else:
    secret_dir = artifacts_dir()
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        secret_file = os.path.join(secret_dir, '.secret')
        if os.path.exists(secret_file):
            with open(secret_file, 'rb') as f:
                secret_key = f.read()
        else:
            secret_key = os.urandom(32)
            try:
                with open(secret_file, 'wb') as f:
                    f.write(secret_key)
            except OSError:
                pass

app.config['SECRET_KEY'] = secret_key
app.config['SITE_URL'] = (os.environ.get('SITE_URL') or 'https://opendecks.ca').strip().rstrip('/')
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = is_vercel
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['ADMIN_USERS'] = os.environ.get('ADMIN_USERS', '')
app.config['WTF_CSRF_TIME_LIMIT'] = None

csrf = CSRFProtect(app)
init_schema()


@app.after_request
def secure_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    if os.environ.get('VERCEL_ENV') == 'preview':
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


app.template_filter('iso_day')(iso_day)
app.template_filter('long_date')(long_date)


@app.errorhandler(413)
def too_large(_e):
    message = 'file too damn thicc (max 2MB per image).'
    if request.path in ('/upload-image', '/preview-markdown'):
        return jsonify({'error': message}), 413
    return message, 413


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
