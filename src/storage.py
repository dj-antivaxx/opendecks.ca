import os
import re
import uuid

from content import IMAGE_MAX_BYTES, is_hosted_url
from runtime import artifacts_dir, on_vercel

MAGIC_TYPES = (
    (b'\xff\xd8\xff', 'jpg', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'png', 'image/png'),
    (b'GIF87a', 'gif', 'image/gif'),
    (b'GIF89a', 'gif', 'image/gif'),
)


def _detect_image(data):
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp', 'image/webp'
    for magic, ext, mime in MAGIC_TYPES:
        if data.startswith(magic):
            return ext, mime
    return None, None


def local_upload_dir():
    if on_vercel():
        raise RuntimeError('ayyyy! refusing to store uploads on the Vercel temporary disk!!!')
    return artifacts_dir('uploads')


def validate_image_bytes(data):
    if not data:
        return None, 'no image uploaded.'
    if len(data) > IMAGE_MAX_BYTES:
        return None, 'image must be 2MB or smaller.'
    ext, mime = _detect_image(data)
    if not ext:
        return None, 'image must be jpeg, png, webp, or gif.'
    return (ext, mime), None


def save_image_bytes(data):
    checked, err = validate_image_bytes(data)
    if err:
        return None, err

    ext, mime = checked
    filename = f'{uuid.uuid4().hex}.{ext}'
    token = os.environ.get('BLOB_READ_WRITE_TOKEN')
    if on_vercel() and not token:
        return None, 'image upload is unavailable.'
    if token:
        try:
            import vercel_blob
            result = vercel_blob.put(
                f'blog/{filename}',
                data,
                {
                    'addRandomSuffix': 'false',
                    'contentType': mime,
                    'allowOverwrite': False,
                },
            )
            url = result.get('url') if isinstance(result, dict) else getattr(result, 'url', None)
            if not url:
                return None, 'image upload failed.'
            return url, None
        except Exception as e:
            print(f'blob ooo upload error: {e}')
            return None, 'image upload failed.'

    dest_dir = local_upload_dir()
    dest = os.path.join(dest_dir, filename)
    with open(dest, 'wb') as f:
        f.write(data)
    return f'/uploads/{filename}', None


def delete_hosted_image(url):
    if not is_hosted_url(url):
        return
    if url.startswith('/uploads/'):
        if on_vercel():
            return
        name = url.rsplit('/', 1)[-1]
        if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|png|gif|webp)', name):
            return
        try:
            os.remove(os.path.join(local_upload_dir(), name))
        except OSError:
            pass
        return
    if not os.environ.get('BLOB_READ_WRITE_TOKEN'):
        return
    try:
        import vercel_blob
        vercel_blob.delete(url)
    except Exception as e:
        print(f'ooo blob delete eeerror: {e}')
