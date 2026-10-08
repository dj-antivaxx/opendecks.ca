import os
import sys
import traceback

# Find and add 'src' directory to the Python path using multiple path candidates
src_candidates = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')),
    os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')),
    os.path.abspath(os.path.join(os.getcwd(), 'src')),
]

for candidate in src_candidates:
    if os.path.exists(candidate):
        sys.path.insert(0, candidate)
        break

try:
    from src.app import app
except Exception:
    traceback.print_exc()

    def app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        return [b'service unavailable']
