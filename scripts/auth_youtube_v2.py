"""
YouTube OAuth — writes auth URL to file, then starts local server waiting for callback.
Run this, then open auth_url.txt URL in browser and click Allow.
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(Path(__file__).parent.parent / '.env')

CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')
TOKEN_PATH = os.getenv('YOUTUBE_TOKEN_PATH', 'youtube_token.json')
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube'
]

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env")
    sys.exit(1)

client_config = {
    "web": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

# Generate auth URL without starting server yet — write to file
flow.redirect_uri = "http://localhost:8085"
auth_url, state = flow.authorization_url(
    access_type='offline',
    prompt='consent'
)

url_file = Path(__file__).parent.parent / 'auth_url.txt'
url_file.write_text(auth_url)
print(f"AUTH_URL={auth_url}")
print(f"\nURL written to: {url_file}")
print(f"\nWaiting for OAuth callback on http://localhost:8085 ...")
sys.stdout.flush()

# Now start local server — blocks until callback received
import wsgiref.simple_server
import urllib.parse

class _WSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    def log_message(self, *args): pass

received_code = [None]

def wsgi_app(environ, start_response):
    query = urllib.parse.parse_qs(environ.get('QUERY_STRING', ''))
    code = query.get('code', [None])[0]
    received_code[0] = code
    start_response('200 OK', [('Content-Type', 'text/html')])
    return [b'<h1>Authorization complete. You can close this tab.</h1>']

server = wsgiref.simple_server.make_server('localhost', 8085, wsgi_app,
                                            handler_class=_WSGIRequestHandler)
server.handle_request()

code = received_code[0]
if not code:
    print("ERROR: No code received")
    sys.exit(1)

print(f"\nCode received. Exchanging for tokens...")
sys.stdout.flush()

flow.fetch_token(code=code, state=state)
creds = flow.credentials

token_file = Path(TOKEN_PATH) if not TOKEN_PATH.startswith('/opt') else Path('youtube_token.json')
token_file.parent.mkdir(parents=True, exist_ok=True)
token_file.write_text(creds.to_json())

print(f"✓ Token saved to: {token_file}")
url_file.unlink(missing_ok=True)
