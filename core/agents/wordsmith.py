"""
WORDSMITH — Script generation agent.
Uses Claude API with soul.md as system prompt.
Includes duration estimation and content safety checks.
"""

import os
import logging
import anthropic
from core.soul import Soul
from core.registry import VideoRegistry

log = logging.getLogger('forge.wordsmith')

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-opus-4-7')

FORMAT_CONFIGS = {
    'youtube_long': {
        'max_words': 1400,
        'structure': 'Hook (5s) → Problem (30s) → Breakdown 3 points → Story/Example → Action steps → Close with CTA',
        'tone_note': 'Long-form. Depth over brevity. Three structured points minimum.',
    },
    'youtube_short': {
        'max_words': 450,
        'structure': 'Hook → Core insight → One clear takeaway → CTA',
        'tone_note': 'Tight. Every word earns its place.',
    },
    'tiktok': {
        'max_words': 130,
        'structure': 'Hook (0-3s) → The truth → Leave them sitting with it',
        'tone_note': 'Vertical video. Punchy. First 3 seconds decide everything.',
    },
    'reels': {
        'max_words': 160,
        'structure': 'Hook → Problem → Answer → Challenge',
        'tone_note': 'Fast. Direct. End with a specific challenge or question.',
    },
    'linkedin': {
        'max_words': 220,
        'structure': 'Hook → Professional insight → 3 bullets → CTA to connect/comment',
        'tone_note': 'Professional but human. No jargon without purpose.',
    },
}

WORDS_PER_MINUTE = 140


class Wordsmith:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    def generate(self, video_id: str, soul_name: str, topic: str,
                 format: str = 'youtube_long', context: str = '',
                 max_words: int = None, delay: int = 0) -> dict:
        import time
        if delay:
            time.sleep(delay)

        soul = Soul(soul_name)
        reg = VideoRegistry()
        reg.update(video_id, status='writing')

        fmt = FORMAT_CONFIGS.get(format, FORMAT_CONFIGS['youtube_long'])
        word_limit = max_words or fmt['max_words']

        user_prompt = self._build_user_prompt(topic=topic, fmt=fmt, word_limit=word_limit, context=context)

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=soul.system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}]
        )

        script = response.content[0].text.strip()
        word_count = len(script.split())
        duration_secs = int((word_count / WORDS_PER_MINUTE) * 60)

        script_path = self._save(video_id, script)
        reg.update(video_id, script_path=script_path, status='scripted')

        log.info(f"[wordsmith] {video_id} → {word_count} words, ~{duration_secs}s")
        return {
            'video_id': video_id,
            'script': script,
            'script_path': script_path,
            'word_count': word_count,
            'duration_secs': duration_secs,
            'format': format,
        }

    def _build_user_prompt(self, topic: str, fmt: dict, word_limit: int, context: str) -> str:
        ctx_block = f"\n\nContext/research:\n{context[:600]}" if context else ''
        return (
            f"Write a complete {fmt['tone_note']} script on this topic:\n\n"
            f"**{topic}**{ctx_block}\n\n"
            f"Structure: {fmt['structure']}\n\n"
            f"Requirements:\n"
            f"- Maximum {word_limit} words (strict)\n"
            f"- Write ONLY the spoken script — no stage directions, no [pause] markers, no formatting headers\n"
            f"- Do not include any music cues, B-roll notes, or visual directions\n"
            f"- Begin with the hook. End with the close. Nothing else.\n"
            f"- Stay completely in character as defined by your identity above"
        )

    def _save(self, video_id: str, script: str) -> str:
        media_dir = os.getenv('FORGE_MEDIA_DIR', '/opt/forge/media')
        job_dir = os.path.join(media_dir, video_id)
        os.makedirs(job_dir, exist_ok=True)
        path = os.path.join(job_dir, 'script.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(script)
        return path
