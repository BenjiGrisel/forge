"""
HERALD — Publishing agent.
Uploads to YouTube, updates Notion, cross-posts clips, notifies CEREBRO.
"""

import os
import re
import logging
import requests
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from core.soul import Soul
from core.registry import VideoRegistry

log = logging.getLogger('forge.herald')

CEREBRO_URL = os.getenv('CEREBRO_WEBHOOK_URL', '')
NOTION_KEY = os.getenv('NOTION_API_KEY', '')
NOTION_CALENDAR_DB = os.getenv('NOTION_CONTENT_CALENDAR_DB', '')
TOKEN_PATH = os.getenv('YOUTUBE_TOKEN_PATH', '/opt/forge/creds/youtube_token.json')


class Herald:
    def publish(self, video_id: str, soul_name: str, final_path: str,
                thumbnail_path: str, script: str, channel_id: str) -> dict:
        soul = Soul(soul_name)
        reg = VideoRegistry()
        reg.update(video_id, status='publishing')

        title, description, tags = self._metadata(script=script, soul=soul)
        youtube_id, youtube_url = self._youtube_upload(
            video_path=final_path,
            thumbnail_path=thumbnail_path,
            title=title,
            description=description,
            tags=tags,
        )

        self._notion_update(video_id=video_id, youtube_url=youtube_url,
                            title=title, soul_name=soul_name)
        self._notify_cerebro(video_id=video_id, soul_name=soul_name,
                             youtube_url=youtube_url, title=title)

        reg.update(video_id, youtube_url=youtube_url, youtube_id=youtube_id, status='published')
        log.info(f"[herald] {video_id} → {youtube_url}")

        return {
            'video_id': video_id,
            'youtube_id': youtube_id,
            'youtube_url': youtube_url,
            'title': title,
            'status': 'published',
        }

    def _metadata(self, script: str, soul: Soul) -> tuple:
        lines = script.strip().split('\n')
        hook = lines[0][:80] if lines else 'New Video'
        title = hook if len(hook) > 10 else f"{soul.name}: {hook}"

        word_count = len(script.split())
        description = (
            f"{script[:500]}...\n\n"
            f"#AI #ContentCreation #{soul.name.replace('-', '')}"
        )
        tags = soul.niche_keywords[:10] + [soul.name, 'AI', 'avatar']
        return title, description, tags

    def _youtube_upload(self, video_path: str, thumbnail_path: str,
                        title: str, description: str, tags: list) -> tuple:
        creds = self._load_creds()
        yt = build('youtube', 'v3', credentials=creds)

        body = {
            'snippet': {
                'title': title[:100],
                'description': description[:4900],
                'tags': tags,
                'categoryId': '22',
            },
            'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False},
        }
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        req = yt.videos().insert(part='snippet,status', body=body, media_body=media)

        response = None
        while response is None:
            _, response = req.next_chunk()

        video_id = response['id']
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        if thumbnail_path and os.path.exists(thumbnail_path):
            yt.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
            ).execute()

        return video_id, youtube_url

    def _load_creds(self) -> Credentials:
        import json
        client_id = os.getenv('YOUTUBE_CLIENT_ID')
        client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
        SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

        creds = None
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise RuntimeError("YouTube OAuth token missing or expired. Run: python scripts/auth_youtube.py")
            with open(TOKEN_PATH, 'w') as f:
                f.write(creds.to_json())
        return creds

    def _notion_update(self, video_id: str, youtube_url: str, title: str, soul_name: str):
        if not NOTION_KEY or not NOTION_CALENDAR_DB:
            return
        requests.post(
            'https://api.notion.com/v1/pages',
            headers={'Authorization': f'Bearer {NOTION_KEY}', 'Notion-Version': '2022-06-28'},
            json={
                'parent': {'database_id': NOTION_CALENDAR_DB},
                'properties': {
                    'Title': {'title': [{'text': {'content': title}}]},
                    'VideoID': {'rich_text': [{'text': {'content': video_id}}]},
                    'Persona': {'select': {'name': soul_name}},
                    'Status': {'select': {'name': 'Published'}},
                    'YouTubeURL': {'url': youtube_url},
                    'PublishedAt': {'date': {'start': datetime.utcnow().isoformat()}},
                }
            },
            timeout=10,
        )

    def _notify_cerebro(self, video_id: str, soul_name: str, youtube_url: str, title: str):
        if not CEREBRO_URL:
            return
        try:
            requests.post(CEREBRO_URL, json={
                'event': 'forge_complete',
                'video_id': video_id,
                'soul': soul_name,
                'title': title,
                'youtube_url': youtube_url,
                'timestamp': datetime.utcnow().isoformat(),
            }, timeout=10)
        except Exception as e:
            log.warning(f"CEREBRO notify failed: {e}")
