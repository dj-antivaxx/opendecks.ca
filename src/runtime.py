import os


def on_vercel():
    return os.environ.get('VERCEL') == '1' or 'VERCEL' in os.environ


def ensure_writable(preferred, fallback):
    try:
        os.makedirs(preferred, exist_ok=True)
        probe = os.path.join(preferred, '.write_test')
        with open(probe, 'w') as handle:
            handle.write('ok')
        os.remove(probe)
        return preferred
    except OSError:
        os.makedirs(fallback, exist_ok=True)
        return fallback


def artifacts_dir(*parts):
    root = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts')
    return ensure_writable(
        os.path.join(root, *parts),
        os.path.join('/tmp/artifacts', *parts),
    )
