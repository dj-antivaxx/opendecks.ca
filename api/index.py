import os
import sys
import traceback

# Add 'src' directory to the path so nested imports work on Vercel
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from src.app import app
except Exception as e:
    tb = traceback.format_exc()
    
    def app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'text/html; charset=utf-8')]
        start_response(status, headers)
        
        html = f"""
        <html>
        <head><title>Startup Error</title></head>
        <body style="font-family: sans-serif; padding: 20px; background: #fff5f5; color: #900;">
            <h1>Startup Exception Captured</h1>
            <pre style="background: #fee; padding: 15px; border: 1px solid #fcc; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;">{tb}</pre>
        </body>
        </html>
        """
        return [html.encode('utf-8')]
