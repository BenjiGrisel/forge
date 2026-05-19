"""
VISUAL — Avatar video agent. Modular: HeyGen (cloud), D-ID (cloud fallback), LivePortrait (local).
Switch with VISUAL_PROVIDER env var — no code changes.
"""

import os
import time
import logging
import requests
from core.soul import Soul
from core.registry import VideoRegistry

log = logging.getLogger('forge.visual')

PROVIDER = os.getenv('VISUAL_PROVIDER', 'heygen')
HEYGEN_KEY = os.getenv('HEYGEN_API_KEY', '')
DID_KEY = os.getenv('DID_API_KEY', '')
LIVEPORTRAIT_HOST = os.getenv('LIVEPORTRAIT_HOST', 'http://localhost:7860')

FORMAT_DIMENSIONS = {
    'youtube_long': {'width': 1920, 'height': 1080, 'aspect_ratio': '16:9'},
    'youtube_short': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'},
    'tiktok': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'},
    'reels': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'},
    'linkedin': {'width': 1920, 'height': 1080, 'aspect_ratio': '16:9'},
}


class VisualAgent:
    def generate(self, video_id: str, soul_name: str, audio_path: str,
                 format: str = 'youtube_long', provider: str = None) -> dict:
        soul = Soul(soul_name)
        reg = VideoRegistry()
        reg.update(video_id, status='rendering')

        dims = FORMAT_DIMENSIONS.get(format, FORMAT_DIMENSIONS['youtube_long'])
        active_provider = provider or PROVIDER

        if active_provider == 'heygen':
            result = self._heygen_submit(soul=soul, audio_path=audio_path, dims=dims)
        elif active_provider == 'did':
            result = self._did_submit(soul=soul, audio_path=audio_path)
        elif active_provider == 'liveportrait':
            result = self._liveportrait(soul=soul, audio_path=audio_path, video_id=video_id)
        else:
            raise ValueError(f"Unknown visual provider: {active_provider}")

        reg.update(video_id, status='rendering')
        log.info(f"[visual] {video_id} → provider={active_provider} job={result.get('provider_job_id')}")
        return {'video_id': video_id, 'provider': active_provider, **result}

    def poll_status(self, provider_job_id: str) -> dict:
        if PROVIDER == 'heygen':
            return self._heygen_poll(provider_job_id)
        elif PROVIDER == 'did':
            return self._did_poll(provider_job_id)
        return {'status': 'unknown'}

    # ── HeyGen ────────────────────────────────────────────────
    def _heygen_submit(self, soul: Soul, audio_path: str, dims: dict) -> dict:
        avatar_id = soul.avatar_id
        if not avatar_id:
            raise ValueError(f"No HeyGen avatar ID for soul: {soul.name}")

        audio_url = self._upload_audio_heygen(audio_path)

        payload = {
            'video_inputs': [{
                'character': {
                    'type': 'avatar',
                    'avatar_id': avatar_id,
                    'avatar_style': soul.avatar_mode,
                },
                'voice': {'type': 'audio', 'audio_url': audio_url},
            }],
            'dimension': {'width': dims['width'], 'height': dims['height']},
            'aspect_ratio': dims['aspect_ratio'],
        }
        r = requests.post(
            'https://api.heygen.com/v2/video/generate',
            json=payload,
            headers={'X-Api-Key': HEYGEN_KEY, 'Content-Type': 'application/json'},
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"HeyGen submit failed: {r.status_code} {r.text[:300]}")
        job_id = r.json()['data']['video_id']
        return {'provider_job_id': job_id, 'video_path': None, 'polling_required': True}

    def _heygen_poll(self, job_id: str) -> dict:
        r = requests.get(
            f'https://api.heygen.com/v1/video_status.get?video_id={job_id}',
            headers={'X-Api-Key': HEYGEN_KEY},
            timeout=15,
        )
        if not r.ok:
            return {'status': 'error', 'error': r.text}
        data = r.json().get('data', {})
        status = data.get('status')
        video_url = data.get('video_url')
        return {'status': status, 'video_url': video_url, 'provider_job_id': job_id}

    def _upload_audio_heygen(self, audio_path: str) -> str:
        with open(audio_path, 'rb') as f:
            data = f.read()
        r = requests.post(
            'https://upload.heygen.com/v1/asset',
            data=data,
            headers={'X-Api-Key': HEYGEN_KEY, 'Content-Type': 'audio/mpeg'},
            timeout=120,
        )
        if not r.ok:
            raise RuntimeError(f"HeyGen audio upload failed: {r.status_code} {r.text[:300]}")
        return r.json()['data']['url']

    # ── D-ID ──────────────────────────────────────────────────
    def _did_submit(self, soul: Soul, audio_path: str) -> dict:
        import base64
        with open(audio_path, 'rb') as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        avatar_id = soul.avatar_id or 'amy-jcu7S4DmVL68qnNvmE'
        payload = {
            'source_url': f'https://d-id.com/avatar/{avatar_id}',
            'script': {'type': 'audio', 'audio_url': f'data:audio/mpeg;base64,{audio_b64}'},
        }
        r = requests.post(
            'https://api.d-id.com/talks',
            json=payload,
            headers={'Authorization': f'Basic {DID_KEY}', 'Content-Type': 'application/json'},
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"D-ID submit failed: {r.status_code} {r.text[:300]}")
        job_id = r.json().get('id')
        return {'provider_job_id': job_id, 'video_path': None, 'polling_required': True}

    def _did_poll(self, job_id: str) -> dict:
        r = requests.get(
            f'https://api.d-id.com/talks/{job_id}',
            headers={'Authorization': f'Basic {DID_KEY}'},
            timeout=15,
        )
        data = r.json()
        return {
            'status': data.get('status'),
            'video_url': data.get('result_url'),
            'provider_job_id': job_id,
        }

    # ── LivePortrait (local) ───────────────────────────────────
    def _liveportrait(self, soul: Soul, audio_path: str, video_id: str) -> dict:
        souls_dir = os.getenv('FORGE_SOULS_DIR', '/opt/forge/souls')
        img_path = os.path.join(souls_dir, 'assets', f"{soul.name}-hero.png")
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"LivePortrait needs hero image at: {img_path}")

        media_dir = os.getenv('FORGE_MEDIA_DIR', '/opt/forge/media')
        out_path = os.path.join(media_dir, video_id, 'avatar_raw.mp4')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        with open(img_path, 'rb') as img, open(audio_path, 'rb') as audio:
            r = requests.post(
                f'{LIVEPORTRAIT_HOST}/api/animate',
                files={'image': img, 'audio': audio},
                data={'output_path': out_path},
                timeout=300,
            )
        if not r.ok:
            raise RuntimeError(f"LivePortrait failed: {r.status_code} {r.text[:200]}")

        return {'provider_job_id': None, 'video_path': out_path, 'polling_required': False}
