import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import bleach
import markdown
from markupsafe import Markup

TITLE_MAX = 80
PREVIEW_TEXT_MAX = 600
BODY_WORD_MAX = 3000
BODY_CHAR_MAX = 24000
BODY_IMAGE_MAX = 12
POST_MAX = 30
SLUG_MAX = 60
IMAGE_STORE_MAX = POST_MAX * (BODY_IMAGE_MAX + 1)
IMAGE_LIMIT_ERROR = 'the site has reached its image limit. its not a big limit. please delete a post to make room.'
USERNAME_MIN = 3
USERNAME_MAX = 19
PASSWORD_MIN = 5
PASSWORD_MAX = 69
EMAIL_MAX = 51
IMAGE_MAX_BYTES = 2 * 1024 * 1024
SHOW_TITLE_MAX = 129
SHOW_URL_MAX = 564
SHOW_MAX = 240
DEFAULT_SHOW_TITLE = 'Open Decks Transmission'
DEFAULT_SHOW_MINUTES = 60
NEXT_SHOW_HOURS_MIN = 0.25
NEXT_SHOW_HOURS_MAX = 8
NEXT_SHOW_MINUTES_MIN = 15
NEXT_SHOW_MINUTES_MAX = 480
EASTERN = ZoneInfo('America/New_York')
RESET_TTL = 60 * 60
RESET_KEEP = 60 * 60 * 2
RESET_EMAIL_MAX = 3
RESET_IP_MAX = 10

USERNAME_RE = re.compile(rf'^[a-z0-9_]{{{USERNAME_MIN},{USERNAME_MAX}}}$')
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
IMG_TAG_RE = re.compile(r'<img\b', re.IGNORECASE)
IMG_SRC_RE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)

ALLOWED_TAGS = [
    'p', 'br', 'hr', 'pre', 'code', 'blockquote',
    'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4',
    'em', 'strong', 'a', 'img',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
}
ALLOWED_PROTOCOLS = ['http', 'https']


def normalize_username(value):
    return (value or '').strip().lower()


def normalize_slug(value):
    return (value or '').strip().lower()


def validate_slug(slug):
    if not slug:
        return 'slug is required.'
    if len(slug) > SLUG_MAX:
        return f'slug must be {SLUG_MAX} characters or fewer.'
    if not SLUG_RE.match(slug):
        return 'slug must be lowercase letters, numbers, and hyphens; no other bullshut please.'
    return None


def password_error(password):
    password = password or ''
    if len(password) < PASSWORD_MIN or len(password) > PASSWORD_MAX:
        return f'password must be {PASSWORD_MIN}–{PASSWORD_MAX} characters.'
    return None


def _real_show_date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value or ''):
        return False
    try:
        day = datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return False
    return 1980 <= day.year <= 2100


def canonical_mixcloud(url):
    raw = (url or '').strip()
    if not raw or len(raw) > SHOW_URL_MAX or any(ch in raw for ch in ' \t\r\n'):
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    host = parts.netloc.lower()
    if parts.scheme.lower() != 'https' or host not in ('www.mixcloud.com', 'mixcloud.com'):
        return None
    if parts.query or parts.fragment or parts.username or parts.password:
        return None
    path = parts.path or ''
    if '//' in path or '\\' in path or '..' in path.split('/'):
        return None
    segments = [segment for segment in path.split('/') if segment]
    if not segments:
        return None
    for ch in path:
        if ch in '/._~%-+':
            continue
        if ch.isascii() and ch.isalnum():
            continue
        if not ch.isascii() and ch.isalpha():
            continue
        return None
    if not path.endswith('/'):
        path += '/'
    return f'https://www.mixcloud.com{path}'


def validate_show(title, show_date, mixcloud_url):
    errors = []
    title = (title or '').strip()
    show_date = (show_date or '').strip()
    if not title:
        errors.append('title is required.')
    elif len(title) > SHOW_TITLE_MAX or any(ord(ch) < 32 for ch in title):
        errors.append(f'title must be {SHOW_TITLE_MAX} characters or fewer, on one line.')
    if not _real_show_date(show_date):
        errors.append('date must be a real day, written YYYY-MM-DD.')
    url = canonical_mixcloud(mixcloud_url)
    if not url:
        errors.append('link must be an https mixcloud.com url.')
    return errors, title, show_date, url


def _fourth_friday(year, month):
    first = datetime(year, month, 1)
    offset = (4 - first.weekday()) % 7
    return 1 + offset + 21


def default_next_show(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = now.astimezone(EASTERN)
    for step in range(14):
        month = local.month + step
        year = local.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = _fourth_friday(year, month)
        start = datetime(year, month, day, 21, 0, tzinfo=EASTERN)
        if now < start + timedelta(minutes=DEFAULT_SHOW_MINUTES):
            return {
                'title': DEFAULT_SHOW_TITLE,
                'start': int(start.timestamp()),
                'minutes': DEFAULT_SHOW_MINUTES,
            }
    raise RuntimeError('no upcoming transmission')


def format_eastern(start_epoch):
    moment = datetime.fromtimestamp(int(start_epoch), EASTERN)
    zone = moment.tzname() or 'ET'
    return f"{moment.strftime('%B')} {moment.day}, {moment.year} @ {moment.strftime('%H:%M')} {zone}"


def eastern_clock(start_epoch):
    moment = datetime.fromtimestamp(int(start_epoch), EASTERN)
    return moment.strftime('%Y-%m-%d'), moment.strftime('%H:%M')


def format_hours(minutes):
    hours = float(minutes) / 60
    return f'{hours:.2f}'.rstrip('0').rstrip('.')


def hours_label(hours_text):
    return f'{float(hours_text):.2f}'.rstrip('0').rstrip('.')


def validate_next_show(title, show_date, show_time, hours, now=None):
    errors = []
    title = (title or '').strip()
    show_date = (show_date or '').strip()
    show_time = (show_time or '').strip()
    hours_text = (hours or '').strip()
    if not title:
        errors.append('title is required.')
    elif len(title) > SHOW_TITLE_MAX or any(ord(ch) < 32 for ch in title):
        errors.append(f'title must be {SHOW_TITLE_MAX} characters or fewer')
    if not _real_show_date(show_date):
        errors.append('date incorrect, format: YYYY-MM-DD.')
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', show_time):
        errors.append('time incorrect, must be HH:MM, 24-hour.')
    parsed_minutes = None
    label = None
    if not re.fullmatch(r'\d{1,2}(?:\.\d{1,2})?', hours_text):
        errors.append(f'length incorrect, allowed: {NEXT_SHOW_HOURS_MIN}–{NEXT_SHOW_HOURS_MAX}')
    else:
        parsed_minutes = round(float(hours_text) * 60, 4)
        if not NEXT_SHOW_MINUTES_MIN <= parsed_minutes <= NEXT_SHOW_MINUTES_MAX:
            errors.append(f'lengtho incorrecto. we need {NEXT_SHOW_HOURS_MIN}–{NEXT_SHOW_HOURS_MAX} hours.')
        else:
            label = hours_label(hours_text)
    start = None
    if not errors:
        naive = datetime.strptime(f'{show_date} {show_time}', '%Y-%m-%d %H:%M')
        start = int(naive.replace(tzinfo=EASTERN).timestamp())
        now_epoch = int((now or datetime.now(timezone.utc)).timestamp())
        if start + parsed_minutes * 60 <= now_epoch:
            errors.append('ERRROR! that show has already ended.')
    return errors, title, start, parsed_minutes, label


def word_count(text):
    return len((text or '').split())


def iso_day(value):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)[:10]


def long_date(value):
    if not value:
        return ''
    if hasattr(value, 'month'):
        return f'{value.strftime("%B")} {value.day}, {value.year}'
    text = str(value)[:10]
    try:
        year, month, day = text.split('-')
        months = (
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December',
        )
        return f'{months[int(month) - 1]} {int(day)}, {year}'
    except (ValueError, IndexError):
        return text


def clip_text(text, limit=160):
    text = ' '.join((text or '').split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 3].rsplit(' ', 1)[0]
    if not cut:
        cut = text[:limit - 3]
    return cut + '...'


def render_markdown(body_md):
    raw_html = markdown.markdown(
        body_md or '',
        extensions=['sane_lists', 'nl2br'],
        output_format='html',
    )
    cleaned = bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    cleaned = re.sub(r'<a\b', '<a rel="ugc nofollow"', cleaned, flags=re.IGNORECASE)
    return Markup(cleaned)


def is_hosted_url(url):
    if not url:
        return False
    if url.startswith('/uploads/'):
        return True
    lowered = url.lower()
    return lowered.startswith('https://') and 'blob.vercel-storage.com' in lowered


def hosted_urls(preview_url, body_md):
    found = []
    if preview_url:
        found.append(preview_url)
    found.extend(IMG_SRC_RE.findall(str(render_markdown(body_md or ''))))
    return [url for url in found if is_hosted_url(url)]


def count_body_images(body_md):
    if not body_md:
        return 0
    return len(IMG_TAG_RE.findall(str(render_markdown(body_md))))


def validate_post_fields(title, preview_text, body_md):
    errors = []
    title = (title or '').strip()
    preview_text = (preview_text or '').strip()
    body_md = body_md or ''

    if not title:
        errors.append('title is required.')
    elif len(title) > TITLE_MAX:
        errors.append(f'title must be {TITLE_MAX} characters or fewer. no epic poems please.')

    if not preview_text:
        errors.append('preview text is required.')
    elif len(preview_text) > PREVIEW_TEXT_MAX:
        errors.append(f'preview text must be {PREVIEW_TEXT_MAX} characters or fewer.')

    if len(body_md) > BODY_CHAR_MAX:
        errors.append(f'post must be {BODY_CHAR_MAX} characters or fewer. we have to have a strict limit because we have to pay for every symbol that you type here, and we are not made of money.')
    else:
        if word_count(body_md) > BODY_WORD_MAX:
            errors.append(f'post must be {BODY_WORD_MAX} words or fewer. we have to have a strict limit because we have to pay for every word that you type here, and we are not made of money.')
        if count_body_images(body_md) > BODY_IMAGE_MAX:
            errors.append(f'at most {BODY_IMAGE_MAX} images in the post body. we have to have a strict limit because we have to pay for every image that you put out here, and we are not made of money.')

    return errors
