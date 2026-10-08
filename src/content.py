import re

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
USERNAME_MAX = 32
PASSWORD_MIN = 8
PASSWORD_MAX = 128
EMAIL_MAX = 100
IMAGE_MAX_BYTES = 2 * 1024 * 1024

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
