"""
Step 2: Exchange the authorization code for tokens.
Run this after pasting your auth code from Google.
Usage: python scripts/auth_step2_exchange.py CODE_FROM_GOOGLE
"""
import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')
TOKEN_PATH = os.getenv('YOUTUBE_TOKEN_PATH', 'youtube_token.json')

if len(sys.argv) < 2:
    # Try reading from file if no argument
    code_file = Path(__file__).parent.parent / 'auth_code.txt'
    if code_file.exists():
        code = code_file.read_text().strip()
    else:
        print("Usage: python scripts/auth_step2_exchange.py YOUR_AUTH_CODE")
        print("Or save the code to auth_code.txt")
        sys.exit(1)
else:
    code = sys.argv[1].strip()

resp = requests.post('https://oauth2.googleapis.com/token', data={
    'code': code,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
    'grant_type': 'authorization_code'
})

if resp.status_code != 200:
    print(f"ERROR: {resp.status_code} — {resp.text}")
    sys.exit(1)

token_data = resp.json()

# Format to match google-auth-oauthlib's expected structure
token_json = {
    "token": token_data.get("access_token"),
    "refresh_token": token_data.get("refresh_token"),
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scopes": [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube"
    ],
    "expiry": None
}

token_file = Path(TOKEN_PATH) if Path(TOKEN_PATH).is_absolute() else Path('youtube_token.json')
token_file.parent.mkdir(parents=True, exist_ok=True)
token_file.write_text(json.dumps(token_json, indent=2))

print(f"✓ Token saved to: {token_file}")
print(f"✓ Refresh token: {'YES' if token_data.get('refresh_token') else 'NO'}")
