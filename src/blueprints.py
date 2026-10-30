import os
import re
import secrets
import time
from functools import wraps
from xml.sax.saxutils import escape

from flask import (
    Blueprint, Response, current_app, jsonify, redirect, render_template,
    request, send_from_directory, session, url_for,
)
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import PasswordField, StringField, SubmitField, TextAreaField
from wtforms import validators
from werkzeug.security import check_password_hash, generate_password_hash

from content import (
    BODY_CHAR_MAX, BODY_IMAGE_MAX, EMAIL_MAX, IMAGE_LIMIT_ERROR, IMAGE_STORE_MAX,
    PASSWORD_MAX, POST_MAX, PREVIEW_TEXT_MAX, RESET_EMAIL_MAX, RESET_IP_MAX,
    RESET_KEEP, RESET_TTL, SHOW_MAX, SHOW_TITLE_MAX, SHOW_URL_MAX,
    SLUG_MAX, TITLE_MAX, USERNAME_MAX, USERNAME_MIN, USERNAME_RE, clip_text,
    count_body_images, default_next_show, eastern_clock, format_eastern, format_hours,
    hosted_urls, is_hosted_url, iso_day, normalize_slug, normalize_username,
    password_error, render_markdown, validate_next_show, validate_post_fields,
    validate_show, validate_slug,
)
from database import (
    clear_custom_next_show, count_posts, count_reset_requests, count_shows,
    create_post, create_reset, create_show, create_user, delete_post, delete_show,
    delete_stored_image, forget_reset_token, get_custom_next_show, get_post_by_slug,
    get_session_user, get_show, get_user_by_email, get_user_by_username,
    get_valid_reset, hash_reset_token, list_post_media, list_posts, list_shows,
    list_stored_images, purge_resets, record_stored_image, reset_password,
    save_custom_next_show, slug_exists, update_login_meta, update_post, update_show,
)
from meta import client_meta
from notify import mail_configured, send_discord, send_email
from runtime import on_vercel
from storage import delete_hosted_image, local_upload_dir, save_image_bytes, validate_image_bytes

home = Blueprint('home', __name__)

UPLOAD_NAME_RE = re.compile(r'^[a-f0-9]{32}\.(jpg|png|gif|webp)$')
HOME_DESCRIPTION = 'Open Decks is an epic website dedicated to connecting DJs and other beings.'


def site_url():
    return current_app.config['SITE_URL']


def reset_page_origin():
    """Local reset links stay on this machine. Vercel links use SITE_URL."""
    if on_vercel():
        return site_url()
    origin = request.host_url.rstrip('/')
    if any(ch in origin for ch in ' \r\n'):
        return site_url()
    return origin


def page_meta(title, description, path, robots=None, og_type='website', og_image=None, json_ld=None):
    return {
        'page_title': title,
        'page_description': description,
        'canonical_path': path,
        'robots': robots,
        'og_type': og_type,
        'og_image': og_image,
        'json_ld': json_ld,
    }


def public_image(url):
    if not url:
        return None
    if url.startswith('https://') or url.startswith('http://'):
        return url
    base = site_url()
    if not url.startswith('/'):
        url = '/' + url
    return base + url


def post_json_ld(post, image):
    site = site_url()
    data = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'headline': post['title'],
        'description': clip_text(post['preview_text']),
        'datePublished': iso_day(post['created_at']),
        'dateModified': iso_day(post['updated_at']),
        'author': {'@type': 'Person', 'name': post['author_username']},
        'mainEntityOfPage': f"{site}/blog/{post['slug']}",
    }
    if image:
        data['image'] = image
    return data


def admin_set():
    raw = current_app.config.get('ADMIN_USERS') or os.environ.get('ADMIN_USERS', '')
    return {n.strip().lower() for n in raw.split(',') if n.strip()}


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    user = get_session_user(user_id)
    if not user:
        session.clear()
        return None
    stamp = int(user['password_changed_at'] or 0)
    if int(session.get('pw_stamp') or 0) != stamp:
        session.clear()
        return None
    return user


def start_session(user):
    session.clear()
    session['user_id'] = user['id']
    session['pw_stamp'] = int(user.get('password_changed_at') or 0)
    session.permanent = True


def is_admin(user):
    return bool(user) and user['username'] in admin_set()


def can_manage(user, post):
    return bool(user) and (user['id'] == post['author_id'] or is_admin(user))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for('home.index'))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not is_admin(user):
            return redirect(url_for('home.index'))
        return fn(*args, **kwargs)
    return wrapper


class LoginForm(FlaskForm):
    username = StringField(
        '',
        validators=[validators.InputRequired(message='username needed.'), validators.Length(max=USERNAME_MAX)],
        render_kw={'placeholder': 'username', 'autocomplete': 'username', 'spellcheck': 'false'},
    )
    password = PasswordField(
        '',
        validators=[validators.InputRequired(message='password required.'), validators.Length(max=PASSWORD_MAX)],
        render_kw={'placeholder': 'password', 'autocomplete': 'current-password'},
    )
    login = SubmitField('log in')


class SignupForm(FlaskForm):
    username = StringField(
        '',
        validators=[validators.InputRequired(message='user who?'), validators.Length(max=USERNAME_MAX)],
        render_kw={'placeholder': 'username', 'autocomplete': 'username', 'spellcheck': 'false'},
    )
    password = PasswordField(
        '',
        validators=[validators.InputRequired(message='password what?'), validators.Length(max=PASSWORD_MAX)],
        render_kw={'placeholder': 'password', 'autocomplete': 'new-password'},
    )
    email = StringField(
        '',
        filters=[lambda value: (value or '').strip().lower()],
        validators=[
            validators.DataRequired(message='email needed.'),
            validators.Email(message='invalid email address. u mad bro?'),
            validators.Length(max=EMAIL_MAX),
        ],
        render_kw={'placeholder': 'email', 'autocomplete': 'email', 'spellcheck': 'false'},
    )
    od_hp = StringField('', render_kw={'tabindex': '-1', 'autocomplete': 'off', 'aria-hidden': 'true'})
    signup = SubmitField('sign up*')


class PostForm(FlaskForm):
    title = StringField(
        'title',
        validators=[validators.InputRequired(), validators.Length(max=TITLE_MAX)],
        render_kw={'maxlength': TITLE_MAX},
    )
    slug = StringField(
        'slug',
        validators=[
            validators.Optional(),
            validators.Length(max=SLUG_MAX, message=f'slug must be {SLUG_MAX} characters or fewer. what are you thinking you writing over here? an epic poem?'),
        ],
        render_kw={
            'maxlength': SLUG_MAX,
            'spellcheck': 'false',
            'autocapitalize': 'off',
            'autocomplete': 'off',
            'placeholder': 'my-post',
        },
    )
    preview_text = TextAreaField(
        'preview text',
        validators=[validators.InputRequired(), validators.Length(max=PREVIEW_TEXT_MAX)],
        render_kw={'maxlength': PREVIEW_TEXT_MAX, 'rows': 6},
    )
    body_md = TextAreaField(
        'body',
        validators=[validators.Length(max=BODY_CHAR_MAX)],
        render_kw={'rows': 16, 'maxlength': BODY_CHAR_MAX},
    )
    preview_image = FileField('preview image')
    save = SubmitField('save')


class ShowForm(FlaskForm):
    title = StringField(
        'title',
        validators=[
            validators.InputRequired(message='title is required.'),
            validators.Length(max=SHOW_TITLE_MAX, message=f'title must be {SHOW_TITLE_MAX} characters or fewer.'),
        ],
        render_kw={'maxlength': SHOW_TITLE_MAX},
    )
    show_date = StringField(
        'date',
        validators=[
            validators.InputRequired(message='date is required.'),
            validators.Length(max=10, message='date must be written YYYY-MM-DD.'),
        ],
        render_kw={
            'placeholder': 'YYYY-MM-DD',
            'maxlength': 10,
            'spellcheck': 'false',
            'autocomplete': 'off',
        },
    )
    mixcloud_url = StringField(
        'mixcloud link',
        validators=[
            validators.InputRequired(message='mixcloud link is required.'),
            validators.Length(max=SHOW_URL_MAX, message=f'link must be {SHOW_URL_MAX} characters or fewer.'),
        ],
        render_kw={
            'placeholder': 'https://www.mixcloud.com/...',
            'maxlength': SHOW_URL_MAX,
            'spellcheck': 'false',
            'autocomplete': 'off',
        },
    )
    save = SubmitField('save')


class NextShowForm(FlaskForm):
    title = StringField(
        'title',
        validators=[
            validators.InputRequired(message='title is required.'),
            validators.Length(max=SHOW_TITLE_MAX, message=f'title must be {SHOW_TITLE_MAX} characters or fewer.'),
        ],
        render_kw={'maxlength': SHOW_TITLE_MAX},
    )
    show_date = StringField(
        'date',
        validators=[
            validators.InputRequired(message='date is required.'),
            validators.Length(max=10, message='date must be written YYYY-MM-DD.'),
        ],
        render_kw={'placeholder': 'YYYY-MM-DD', 'maxlength': 10, 'spellcheck': 'false', 'autocomplete': 'off'},
    )
    show_time = StringField(
        'time (eastern)',
        validators=[
            validators.InputRequired(message='time is required.'),
            validators.Length(max=5, message='time must be HH:MM.'),
        ],
        render_kw={'placeholder': '21:00', 'maxlength': 5, 'spellcheck': 'false', 'autocomplete': 'off'},
    )
    hours = StringField(
        'length (hours)',
        validators=[
            validators.InputRequired(message='length is required.'),
            validators.Length(max=4),
        ],
        render_kw={'placeholder': '1', 'maxlength': 4, 'inputmode': 'decimal', 'spellcheck': 'false'},
    )
    save = SubmitField('save')


class ForgotForm(FlaskForm):
    email = StringField(
        '',
        filters=[lambda value: (value or '').strip().lower()],
        validators=[
            validators.DataRequired(message='email needed.'),
            validators.Email(message='that does not look like an email.'),
            validators.Length(max=EMAIL_MAX),
        ],
        render_kw={'placeholder': 'email', 'autocomplete': 'email', 'spellcheck': 'false'},
    )
    od_hp = StringField('', render_kw={'tabindex': '-1', 'autocomplete': 'off', 'aria-hidden': 'true'})
    send = SubmitField('send reset link')


class ResetForm(FlaskForm):
    password = PasswordField(
        '',
        validators=[validators.InputRequired(message='password what?'), validators.Length(max=PASSWORD_MAX)],
        render_kw={'placeholder': 'new password', 'autocomplete': 'new-password'},
    )
    confirm = PasswordField(
        '',
        validators=[
            validators.InputRequired(message='confirm the password.'),
            validators.Length(max=PASSWORD_MAX),
            validators.EqualTo('password', message='those passwords do not match.'),
        ],
        render_kw={'placeholder': 'confirm password', 'autocomplete': 'new-password'},
    )
    save = SubmitField('save password')


@home.app_context_processor
def inject_globals():
    return {
        'current_user': current_user(),
        'is_admin': is_admin,
        'site_url': site_url(),
        'search_index': os.environ.get('VERCEL_ENV') != 'preview',
    }


@home.route('/', methods=['GET', 'POST'])
def index():
    login_form = LoginForm(prefix='login')
    signup_form = SignupForm(prefix='signup')
    user = current_user()
    login_error = None
    signup_error = None
    auth_panel = None

    if request.method == 'POST' and not user:
        if login_form.login.data:
            auth_panel = 'login'
            if login_form.validate():
                login_error = _handle_login(login_form)
                if not login_error:
                    return redirect(url_for('home.index'))
        elif signup_form.signup.data:
            auth_panel = 'signup'
            if signup_form.validate():
                signup_error = _handle_signup(signup_form)
                if not signup_error:
                    return redirect(url_for('home.index'))

    upcoming = _current_next_show()
    return render_template(
        'home.html',
        login_form=login_form,
        signup_form=signup_form,
        shows=list_shows(),
        posts=list_posts(),
        login_error=login_error,
        signup_error=signup_error,
        auth_panel=auth_panel,
        user_is_admin=is_admin(user),
        show_title=upcoming['title'],
        show_when=format_eastern(upcoming['start']),
        next_show={'start': upcoming['start'] * 1000, 'minutes': upcoming['minutes']},
        **page_meta('Open Decks', HOME_DESCRIPTION, '/'),
    )


def _current_next_show():
    """Expired custom shows are ignored. The row stays until the next save or reset."""
    now = int(time.time())
    custom = get_custom_next_show()
    if custom and custom['start'] + custom['minutes'] * 60 > now:
        custom['custom'] = True
        return custom
    show = default_next_show()
    show['custom'] = False
    return show


def _handle_signup(form):
    if (form.od_hp.data or '').strip():
        return 'could not create account.'

    username = normalize_username(form.username.data)
    if not USERNAME_RE.match(username):
        return f'username MUST be {USERNAME_MIN}–{USERNAME_MAX} characters: a–z, 0–9, underscore. these are not the rules we made.'

    password = form.password.data or ''
    pw_error = password_error(password)
    if pw_error:
        return pw_error

    email = (form.email.data or '').strip().lower()
    if not email:
        return 'email needed.'
    if get_user_by_email(email):
        return 'username or email already taken. by yo mama :)'
    if get_user_by_username(username):
        return 'username exists.'

    meta = client_meta(request)
    try:
        user_id = create_user(
            username,
            generate_password_hash(password),
            email,
            meta,
        )
    except Exception as e:
        if 'unique' in str(e).lower():
            return 'username or email already taken.'
        raise

    start_session({'id': user_id})
    send_discord(f'\n *WE WELCOME A NEW GOONER* \n {username} {email or "without fucking email"}')
    return None


def _handle_login(form):
    username = normalize_username(form.username.data)
    user = get_user_by_username(username)
    password = form.password.data or ''
    if not user or not check_password_hash(user['password_hash'], password):
        return 'invalid username or password.'
    update_login_meta(user['id'], client_meta(request))
    start_session(user)
    return None


@home.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home.index'))


@home.route('/terms', methods=['GET'])
def terms():
    return render_template(
        'terms.html',
        **page_meta(
            'terms — Open Decks',
            'terms of use.',
            '/terms',
        ),
    )


def _write_meta(post=None):
    if post:
        return page_meta(
            'edit — Open Decks',
            'edit article',
            f"/blog/{post['slug']}",
            robots='noindex',
        )
    return page_meta('write — Open Decks', 'write yo article.', '/write', robots='noindex')


def _write_page(form, errors, post=None):
    return render_template('write.html', form=form, errors=errors, post=post, **_write_meta(post))


def _missing_post():
    return render_template(
        'post.html',
        post=None,
        body_html=None,
        can_edit=False,
        **page_meta('not found — Open Decks', 'that article can not be found by some reason.', request.path, robots='noindex'),
    ), 404


@home.route('/write', methods=['GET', 'POST'])
@login_required
def write():
    form = PostForm()
    if request.method == 'GET':
        return _write_page(form, [])
    if count_posts() >= POST_MAX:
        return _write_page(form, [f'you cannot create an article since this site is limited to {POST_MAX} articles. this is because we are trying to keep Internet clean. delete one to make room.'])
    if not form.validate_on_submit():
        return _write_page(form, [])

    errors = []
    slug = normalize_slug(form.slug.data)
    slug_error = validate_slug(slug)
    if slug_error:
        errors.append(slug_error)
    elif slug_exists(slug):
        errors.append('someone already used that slug. maybe try a different one?')
    field_errors, image_data = _collect_post_errors(form, existing=None)
    errors.extend(field_errors)
    if errors:
        return _write_page(form, errors)

    preview_url, err = _store_preview(image_data, existing=None)
    if err:
        return _write_page(form, [err])

    title = form.title.data.strip()
    preview = form.preview_text.data.strip()
    try:
        create_post(
            slug,
            title,
            preview,
            preview_url,
            form.body_md.data or '',
            current_user()['id'],
        )
    except Exception as e:
        if 'unique' in str(e).lower():
            return _write_page(form, ['that slug is already used.'])
        raise
    send_discord(f'\n *yo we got a new post!* \n{title}\n{preview}\n{site_url()}/blog/{slug}')
    return redirect(url_for('home.post', slug=slug))


@home.route('/blog/<slug>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(slug):
    post = get_post_by_slug(slug)
    if not post:
        return _missing_post()
    if not can_manage(current_user(), post):
        return redirect(url_for('home.post', slug=slug))

    form = PostForm()
    if request.method == 'GET':
        form.body_md.data = post['body_md']
        form.preview_text.data = post['preview_text']
        form.title.data = post['title']
        return _write_page(form, [], post)
    if not form.validate_on_submit():
        return _write_page(form, [], post)

    field_errors, image_data = _collect_post_errors(form, existing=post)
    if field_errors:
        return _write_page(form, field_errors, post)
    preview_url, err = _store_preview(image_data, existing=post)
    if err:
        return _write_page(form, [err], post)

    old_urls = hosted_urls(post['preview_image_url'], post['body_md'])
    body_md = form.body_md.data or ''
    update_post(
        post['id'],
        form.title.data.strip(),
        form.preview_text.data.strip(),
        preview_url,
        body_md,
    )
    release_hosted(set(old_urls) - set(hosted_urls(preview_url, body_md)))
    return redirect(url_for('home.post', slug=post['slug']))


def _collect_post_errors(form, existing):
    errors = validate_post_fields(form.title.data, form.preview_text.data, form.body_md.data or '')
    preview_url = existing['preview_image_url'] if existing else None
    file = form.preview_image.data
    data = None
    if file and getattr(file, 'filename', None):
        data = file.read()
        _, err = validate_image_bytes(data)
        if err:
            errors.append(err)
            data = None
    elif not preview_url:
        errors.append('due to our site policy, a preview image is required. maybe upload a picture of your cat if you do not have any ideas for an image.')
    return errors, data


def _store_preview(data, existing):
    if data is None:
        url = existing['preview_image_url'] if existing else None
        if not url:
            return None, 'preview image is required.'
        return url, None
    if image_limit_reached():
        return None, IMAGE_LIMIT_ERROR
    url, err = save_image_bytes(data)
    if url:
        record_stored_image(url)
    return url, err


def image_limit_reached():
    return count_hosted_images() >= IMAGE_STORE_MAX


def referenced_hosted_urls():
    urls = set()
    for post in list_post_media():
        urls.update(hosted_urls(post['preview_image_url'], post['body_md']))
    return urls


def count_hosted_images():
    urls = referenced_hosted_urls()
    urls.update(row['url'] for row in list_stored_images())
    return len(urls)


def release_hosted(urls):
    in_use = referenced_hosted_urls()
    for url in urls:
        if not is_hosted_url(url) or url in in_use:
            continue
        delete_hosted_image(url)
        delete_stored_image(url)


@home.route('/blog/<slug>/delete', methods=['POST'])
@login_required
def remove_post(slug):
    post = get_post_by_slug(slug)
    user = current_user()
    if not post:
        return redirect(url_for('home.index'))
    if not can_manage(user, post):
        return redirect(url_for('home.post', slug=slug))
    urls = hosted_urls(post['preview_image_url'], post['body_md'])
    delete_post(post['id'])
    release_hosted(urls)
    return redirect(url_for('home.index'))


@home.route('/blog/<slug>', methods=['GET'])
def post(slug):
    post = get_post_by_slug(slug)
    if not post:
        return _missing_post()
    user = current_user()
    image = public_image(post['preview_image_url'])
    return render_template(
        'post.html',
        post=post,
        body_html=render_markdown(post['body_md']),
        can_edit=can_manage(user, post),
        **page_meta(
            f"{post['title']} — Open Decks",
            clip_text(post['preview_text']),
            f"/blog/{post['slug']}",
            og_type='article',
            og_image=image,
            json_ld=post_json_ld(post, image),
        ),
    )


@home.route('/robots.txt', methods=['GET'])
def robots():
    site = site_url()
    if os.environ.get('VERCEL_ENV') == 'preview':
        body = 'User-agent: *\nDisallow: /\n'
    else:
        body = f'User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n'
    return Response(body, mimetype='text/plain')


@home.route('/sitemap.xml', methods=['GET'])
def sitemap():
    site = site_url()
    posts = list_posts()
    latest = ''
    entries = []
    for post in posts:
        day = iso_day(post['updated_at'])
        if day > latest:
            latest = day
        entries.append((f"{site}/blog/{post['slug']}", day))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        _sitemap_url(site + '/', latest),
    ]
    for loc, day in entries:
        parts.append(_sitemap_url(loc, day))
    parts.append(_sitemap_url(site + '/terms', ''))
    parts.append('</urlset>')
    return Response('\n'.join(parts) + '\n', mimetype='application/xml')


def _sitemap_url(loc, lastmod):
    xml = f'<url><loc>{escape(loc)}</loc>'
    if lastmod:
        xml += f'<lastmod>{escape(lastmod)}</lastmod>'
    return xml + '</url>'


@home.route('/upload-image', methods=['POST'])
@login_required
def upload_image():
    body_md = request.form.get('body_md', '')
    if len(body_md) > BODY_CHAR_MAX:
        return jsonify({'error': f'post must be {BODY_CHAR_MAX} characters or fewer.'}), 400
    if count_body_images(body_md) >= BODY_IMAGE_MAX:
        return jsonify({'error': f'at most {BODY_IMAGE_MAX} images in the post body. right now there is too many. we cannot have them all.'}), 400
    if image_limit_reached():
        return jsonify({'error': IMAGE_LIMIT_ERROR}), 400
    uploaded = request.files.get('image')
    if not uploaded:
        return jsonify({'error': 'no image uploaded.'}), 400
    url, err = save_image_bytes(uploaded.read())
    if err:
        return jsonify({'error': err}), 400
    record_stored_image(url)
    return jsonify({'url': url})


@home.route('/preview-markdown', methods=['POST'])
@login_required
def preview_md():
    body = request.form.get('body_md', '')
    if len(body) > BODY_CHAR_MAX:
        return jsonify({'error': f'post must be {BODY_CHAR_MAX} characters or fewer.'}), 400
    return jsonify({'html': str(render_markdown(body))})


@home.route('/uploads/<filename>', methods=['GET'])
def uploaded_file(filename):
    if on_vercel():
        return 'not found', 404
    if not UPLOAD_NAME_RE.match(filename):
        return 'not found', 404
    return send_from_directory(local_upload_dir(), filename)


def _show_page(form, errors, shows):
    return render_template(
        'episodes.html',
        form=form,
        errors=errors,
        shows=shows,
        **page_meta('episodes — Open Decks', 'edit past episodes.', '/episodes', robots='noindex'),
    )


def _save_show(form, show_id=None):
    if not form.validate_on_submit():
        return None, []
    errors, title, day, url = validate_show(form.title.data, form.show_date.data, form.mixcloud_url.data)
    if errors:
        return None, errors
    try:
        if show_id is None:
            create_show(title, day, url)
        else:
            update_show(show_id, title, day, url)
    except Exception as exc:
        if 'unique' in str(exc).lower():
            return None, ['mixcloud link is already there YO.']
        raise
    return True, []


@home.route('/episodes', methods=['GET', 'POST'])
@admin_required
def episodes():
    form = ShowForm()
    errors = []
    if request.method == 'POST':
        if count_shows() >= SHOW_MAX:
            errors = [f'the list is full, allowed max: ({SHOW_MAX}).']
        else:
            saved, errors = _save_show(form)
            if saved:
                return redirect(url_for('home.episodes'))
    return _show_page(form, errors, list_shows())


@home.route('/episodes/<int:show_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_episode(show_id):
    show = get_show(show_id)
    if not show:
        return redirect(url_for('home.episodes'))
    form = ShowForm()
    errors = []
    if request.method == 'GET':
        form.title.data = show['title']
        form.show_date.data = show['date']
        form.mixcloud_url.data = show['mixcloud_url']
    else:
        saved, errors = _save_show(form, show_id)
        if saved:
            return redirect(url_for('home.episodes'))
    return render_template(
        'episode_edit.html',
        form=form,
        errors=errors,
        show=show,
        **page_meta('edit episode — Open Decks', 'edit a past episode.', request.path, robots='noindex'),
    )


@home.route('/episodes/<int:show_id>/delete', methods=['POST'])
@admin_required
def remove_episode(show_id):
    delete_show(show_id)
    return redirect(url_for('home.episodes'))


def _fill_next_show_form(form, show):
    day, clock = eastern_clock(show['start'])
    form.title.data = show['title']
    form.show_date.data = day
    form.show_time.data = clock
    form.hours.data = show.get('hours') or format_hours(show['minutes'])


@home.route('/next-show', methods=['GET', 'POST'])
@admin_required
def next_show():
    upcoming = _current_next_show()
    form = NextShowForm()
    errors = []
    if request.method == 'POST' and request.form.get('action') == 'reset':
        clear_custom_next_show()
        return redirect(url_for('home.next_show'))
    if request.method == 'GET':
        _fill_next_show_form(form, upcoming)
    elif form.validate_on_submit():
        errors, title, start, minutes, hours_label = validate_next_show(
            form.title.data, form.show_date.data, form.show_time.data, form.hours.data,
        )
        if not errors:
            save_custom_next_show(title, start, minutes, hours_label)
            return redirect(url_for('home.index'))
    return render_template(
        'next_show.html',
        form=form,
        errors=errors,
        custom=upcoming['custom'],
        **page_meta('next show — Open Decks', 'edit the next show', '/next-show', robots='noindex'),
    )


RESET_NOTICE = 'if u have yo email u will see a reset link in ur mailbox. CHECK SPAM FOLDER!'
RESET_SLOW = 'yooo tf u doing dawg slow fucking down okay'
RESET_BAD = 'what the fuck is wrong wit yo reset link'
RESET_UNSENT = 'something is fucked wit email. shit not working bro'
RESET_OFF = 'password reset email is not set up. u fucked.'
TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{32,128}$')


def _deliver_reset(username, email, link):
    if any(ch in link for ch in '\r\n '):
        return False
    subject = 'epic password reset'
    body = (
        'a little bird told me that you wish to reset yo password for our glorious website.\n\n'
        'if thats true, use the link below (good only for 1 hour), and dont forget it next time. write it down on a piece of paper yo\n\n'
        f'{link}\n\n'
        'if you didnt request a password reset, then probably someone is trying to hack your account and our website altogether. no fucking rest for the wicked eh?\n'
    )
    if not mail_configured():
        if not on_vercel():
            print('password reset link:', link)
            return True
        print('password reset email is not FUCKING configured')
        send_discord(f'password reset email FUCKING failed: {username}')
        return False
    if send_email(email, subject, body):
        return True
    send_discord(f'password reset email FUCKING failed: {username}')
    return False


def _request_reset(form):
    if (form.od_hp.data or '').strip():
        return RESET_NOTICE, None
    if on_vercel() and not mail_configured():
        return None, RESET_OFF
    now = int(time.time())
    purge_resets(now - RESET_KEEP)
    ip = client_meta(request).get('ip') or 'unknown'
    if count_reset_requests(now - RESET_TTL, ip=ip) >= RESET_IP_MAX:
        return None, RESET_SLOW
    email = (form.email.data or '').strip().lower()
    user = get_user_by_email(email)
    if user and user.get('email'):
        if count_reset_requests(now - RESET_TTL, user_id=user['id']) < RESET_EMAIL_MAX:
            token = secrets.token_urlsafe(32)
            token_hash = hash_reset_token(token)
            create_reset(user['id'], token_hash, now + RESET_TTL, now, ip)
            link = f"{reset_page_origin()}/reset/{token}"
            if _deliver_reset(user['username'], user['email'], link):
                return RESET_NOTICE, None
            forget_reset_token(token_hash)
            return None, RESET_UNSENT
    create_reset(None, None, now + RESET_TTL, now, ip)
    return RESET_NOTICE, None


@home.route('/forgot', methods=['GET', 'POST'])
def forgot():
    form = ForgotForm()
    notice = None
    error = None
    if request.method == 'POST' and form.validate_on_submit():
        notice, error = _request_reset(form)
    return render_template(
        'forgot.html',
        form=form,
        notice=notice,
        error=error,
        **page_meta(
            'forgot password — Open Decks',
            'reset a password.',
            '/forgot',
            robots='noindex',
        ),
    )


@home.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password_page(token):
    form = ResetForm()
    now = int(time.time())
    purge_resets(now - RESET_KEEP)
    row = None
    if TOKEN_RE.match(token or ''):
        row = get_valid_reset(hash_reset_token(token), now)
    error = None
    if request.method == 'POST':
        if not row:
            return _reset_page(form, False, RESET_BAD)
        if not form.validate_on_submit():
            return _reset_page(form, True, None)
        error = password_error(form.password.data)
        if error:
            return _reset_page(form, True, error)
        if not reset_password(row['id'], row['user_id'], generate_password_hash(form.password.data), now):
            return _reset_page(form, False, RESET_BAD)
        start_session({'id': row['user_id'], 'password_changed_at': now})
        send_discord(f'\n ANOTHER *DUMBASS* FORGOT THEIR PASSWORD. shame on {row["username"]}!!!')
        return redirect(url_for('home.index'))
    if not row:
        return _reset_page(form, False, RESET_BAD)
    return _reset_page(form, True, None)


def _reset_page(form, ok, message):
    return render_template(
        'reset.html',
        form=form,
        ok=ok,
        message=message,
        **page_meta('reset password — Open Decks', 'choose a new password.', '/reset', robots='noindex'),
    )
