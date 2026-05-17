"""
Media Registry — tracks every video through the pipeline.
Notion-backed. Allows resumption from any step if server reboots.
"""

import os
import uuid
from datetime import datetime
from notion_client import Client

NOTION_KEY = os.getenv('NOTION_API_KEY')
DB_ID = os.getenv('NOTION_VIDEO_REGISTRY_DB')


class VideoRegistry:
    def __init__(self):
        self.notion = Client(auth=NOTION_KEY)
        self.db_id = DB_ID

    def init(self, soul_name: str, channel_id: str, format: str) -> str:
        video_id = str(uuid.uuid4())[:8].upper()
        self.notion.pages.create(
            parent={'database_id': self.db_id},
            properties={
                'VideoID': {'title': [{'text': {'content': video_id}}]},
                'Soul': {'rich_text': [{'text': {'content': soul_name}}]},
                'ChannelID': {'rich_text': [{'text': {'content': channel_id}}]},
                'Format': {'select': {'name': format}},
                'Status': {'select': {'name': 'queued'}},
                'CreatedAt': {'date': {'start': datetime.utcnow().isoformat()}},
            }
        )
        return video_id

    def update(self, video_id: str, **fields):
        page = self._find(video_id)
        if not page:
            return
        props = {}
        field_map = {
            'status': ('Status', 'select'),
            'topic': ('Topic', 'rich_text'),
            'script_path': ('ScriptPath', 'rich_text'),
            'audio_path': ('AudioPath', 'rich_text'),
            'video_path': ('VideoPath', 'rich_text'),
            'final_path': ('FinalPath', 'rich_text'),
            'thumbnail_path': ('ThumbnailPath', 'rich_text'),
            'youtube_url': ('YouTubeURL', 'url'),
            'youtube_id': ('YouTubeID', 'rich_text'),
            'error': ('Error', 'rich_text'),
        }
        for key, val in fields.items():
            if key not in field_map:
                continue
            notion_key, kind = field_map[key]
            if kind == 'select':
                props[notion_key] = {'select': {'name': val}}
            elif kind == 'rich_text':
                props[notion_key] = {'rich_text': [{'text': {'content': str(val)}}]}
            elif kind == 'url':
                props[notion_key] = {'url': val}
        if props:
            self.notion.pages.update(page_id=page['id'], properties=props)

    def get(self, video_id: str) -> dict | None:
        page = self._find(video_id)
        if not page:
            return None
        props = page['properties']
        return {
            'video_id': video_id,
            'status': props.get('Status', {}).get('select', {}).get('name'),
            'soul': self._text(props, 'Soul'),
            'topic': self._text(props, 'Topic'),
            'audio_path': self._text(props, 'AudioPath'),
            'video_path': self._text(props, 'VideoPath'),
            'final_path': self._text(props, 'FinalPath'),
            'youtube_url': props.get('YouTubeURL', {}).get('url'),
            'error': self._text(props, 'Error'),
        }

    def _find(self, video_id: str):
        res = self.notion.databases.query(
            database_id=self.db_id,
            filter={'property': 'VideoID', 'title': {'equals': video_id}}
        )
        results = res.get('results', [])
        return results[0] if results else None

    @staticmethod
    def _text(props, key):
        items = props.get(key, {}).get('rich_text', [])
        return items[0]['text']['content'] if items else None
