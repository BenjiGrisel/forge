"""
VOICE — TTS agent. Modular: ElevenLabs (cloud) or Kokoro (local).
Switch provider with VOICE_PROVIDER env var. One-line change.
"""

import os
import logging
import requests
from core.soul import Soul
from core.registry import VideoRegistry

log = logging.getLogger('forge.voice')

PROVIDER = os.getenv('VOICE_PROVIDER', 'elevenlabs')
ELEVENLABS_KEY = os.getenv('ELEVENLABS_API_KEY', '')
KOKORO_HOST = os.getenv('KOKORO_HOST', 'http://localhost:8880')
KOKORO_VOICE = os.getenv('KOKORO_VOICE', 'af_heart')


class VoiceAgent:
    def generate(self, video_id: str, soul_name: str, script: str, delay: int = 0) -> dict:
        import time
        if delay:
            time.sleep(delay)

        soul = Soul(soul_name)
        reg = VideoRegistry()
        reg.update(video_id, status='voicing')

        out_path = self._out_path(video_id)

        if PROVIDER == 'kokoro':
            self._kokoro(script=script, out_path=out_path, voice=KOKORO_VOICE)
        else:
            self._elevenlabs(script=script, out_path=out_path, soul=soul)

        reg.update(video_id, audio_path=out_path, status='voiced')
        log.info(f"[voice] {video_id} → {out_path}")
        return {'video_id': video_id, 'audio_path': out_path, 'provider': PROVIDER}

    def _elevenlabs(self, script: str, out_path: str, soul: Soul):
        voice_id = soul.voice_id
        if not voice_id:
            raise ValueError(f"No ElevenLabs voice ID configured for soul: {soul.name}")

        vp = soul.voice_params
        payload = {
            'text': script,
            'model_id': 'eleven_turbo_v2_5',
            'voice_settings': {
                'stability': vp.get('stability', 0.7),
                'similarity_boost': vp.get('similarity_boost', 0.8),
                'style': vp.get('style', 0.3),
                'use_speaker_boost': True,
            }
        }
        r = requests.post(
            f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
            json=payload,
            headers={'xi-api-key': ELEVENLABS_KEY, 'Accept': 'audio/mpeg'},
            timeout=60,
            stream=True,
        )
        if not r.ok:
            raise RuntimeError(f"ElevenLabs TTS failed: {r.status_code} {r.text[:200]}")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=4096):
                f.write(chunk)

    def _kokoro(self, script: str, out_path: str, voice: str):
        r = requests.post(
            f'{KOKORO_HOST}/tts',
            json={'text': script, 'voice': voice, 'speed': 1.0},
            timeout=120,
        )
        if not r.ok:
            raise RuntimeError(f"Kokoro TTS failed: {r.status_code} {r.text[:200]}")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(r.content)

    def _out_path(self, video_id: str) -> str:
        media_dir = os.getenv('FORGE_MEDIA_DIR', '/opt/forge/media')
        return os.path.join(media_dir, video_id, 'voice.mp3')
