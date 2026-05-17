"""
Soul Loader — reads and parses soul.md files.
Injects VoiceParameters, AvatarMode, and system prompt into API calls.
"""

import os
import re
import yaml
import logging

log = logging.getLogger('forge.soul')

SOULS_DIR = os.getenv('FORGE_SOULS_DIR', '/opt/forge/souls')


class Soul:
    def __init__(self, name: str):
        self.name = name
        self._raw = self._load(name)
        self._meta = self._parse_frontmatter()
        self.system_prompt = self._extract_system_prompt()

    def _load(self, name: str) -> str:
        path = os.path.join(SOULS_DIR, f"{name}.md")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Soul not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_frontmatter(self) -> dict:
        match = re.match(r'^---\n(.*?)\n---\n', self._raw, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except Exception:
                return {}
        return {}

    def _extract_system_prompt(self) -> str:
        content = re.sub(r'^---\n.*?\n---\n', '', self._raw, flags=re.DOTALL).strip()
        return content

    @property
    def voice_params(self) -> dict:
        return self._meta.get('voice_parameters', {
            'stability': 0.7,
            'similarity_boost': 0.8,
            'style': 0.3,
        })

    @property
    def avatar_mode(self) -> str:
        return self._meta.get('avatar_mode', 'normal')

    @property
    def voice_id(self) -> str | None:
        env_key = f"ELEVENLABS_VOICE_ID_{self.name.upper().replace('-', '_')}"
        return os.getenv(env_key) or os.getenv('ELEVENLABS_VOICE_ID_DEFAULT')

    @property
    def avatar_id(self) -> str | None:
        env_key = f"HEYGEN_AVATAR_ID_{self.name.upper().replace('-', '_')}"
        return os.getenv(env_key) or os.getenv('HEYGEN_AVATAR_ID_DEFAULT')

    @property
    def niche_keywords(self) -> list:
        return self._meta.get('niche_keywords', [])

    @property
    def content_themes(self) -> list:
        return self._meta.get('content_themes', [])

    @property
    def format_preferences(self) -> dict:
        return self._meta.get('format_preferences', {})
