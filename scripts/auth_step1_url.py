"""
Step 1: Generate the YouTube OAuth URL and save it to a file.
After running this, open the URL in your browser and click Allow.
Google will show you an authorization code — save it for step 2.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube'
]

scope_str = '%20'.join(SCOPES)
auth_url = (
    f"https://accounts.google.com/o/oauth2/v2/auth"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
    f"&response_type=code"
    f"&scope={scope_str}"
    f"&access_type=offline"
    f"&prompt=consent"
)

# Save to file so Claude can read it
url_file = Path(__file__).parent.parent / 'auth_url.txt'
url_file.write_text(auth_url)
print(auth_url)
print(f"\nURL saved to: {url_file}")
