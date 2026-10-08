import json
import os
import urllib.request

DISCORD_TIMEOUT = 3


def send_discord(text):
    """POST a short note to the channel webhook. Missing config or a Discord
    error must not affect the request that triggered it."""
    url = (os.environ.get('DISCORD_WEBHOOK_URL') or '').strip()
    if not url or not text:
        return False
    body = json.dumps({
        'content': text[:1900],
        'allowed_mentions': {'parse': []},
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'opendecks',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=DISCORD_TIMEOUT) as response:
            response.read()
        return True
    except Exception as exc:
        print('discord notify failed:', type(exc).__name__)
        return False
