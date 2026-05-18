"""
YouTube OAuth Setup — run this ONCE to authorize FORGE to upload videos.
Opens a browser, you log in, token saved to file. Never needs to run again
unless the token expires or you revoke access.

Usage:
  python scripts/auth_youtube.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json

load_dotenv(Path(__file__).parent.parent / '.env')

CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')
TOKEN_PATH = os.getenv('YOUTUBE_TOKEN_PATH', 'youtube_token.json')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube']

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env")
        sys.exit(1)

    os.makedirs(os.path.dirname(TOKEN_PATH) if os.path.dirname(TOKEN_PATH) else '.', exist_ok=True)

    # Check if token already exists and is valid
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if creds and creds.valid:
            print(f"✓ Token already valid: {TOKEN_PATH}")
            return
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'w') as f:
                f.write(creds.to_json())
            print(f"✓ Token refreshed: {TOKEN_PATH}")
            return

    # Build client config inline (no need for downloaded JSON file)
    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    print("\n" + "="*60)
    print("FORGE — YouTube Authorization")
    print("="*60)
    print("A browser window will open. Sign in with the Google account")
    print("that owns the YouTube channel(s) you want FORGE to upload to.")
    print("="*60 + "\n")

    creds = flow.run_local_server(port=0, prompt='consent', open_browser=False)

    with open(TOKEN_PATH, 'w') as f:
        f.write(creds.to_json())

    print(f"\n✓ Authorization complete!")
    print(f"✓ Token saved to: {TOKEN_PATH}")
    print(f"\nNext step: copy this token to your Hetzner server:")
    print(f"  scp {TOKEN_PATH} root@178.156.227.174:/opt/forge/creds/youtube_token.json")

if __name__ == '__main__':
    main()
