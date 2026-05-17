"""
Preflight — checks credit balances and estimates cost before spending API credits.
Returns go/no-go with cost breakdown.
"""

import os
import re
import requests
import logging

log = logging.getLogger('forge.preflight')

ELEVENLABS_KEY = os.getenv('ELEVENLABS_API_KEY', '')
HEYGEN_KEY = os.getenv('HEYGEN_API_KEY', '')

WORDS_PER_MINUTE = 140
CHARS_PER_WORD = 5.5

FORMAT_WORD_TARGETS = {
    'youtube_long': 1200,
    'youtube_short': 400,
    'tiktok': 120,
    'reels': 150,
    'linkedin': 200,
}

RISKY_TOPICS = ['lawsuit against', 'guaranteed returns', 'cure for', 'hack your']


class Preflight:
    def run(self, soul_name: str, topic: str, format: str = 'youtube_long') -> dict:
        word_target = FORMAT_WORD_TARGETS.get(format, 800)
        char_estimate = int(word_target * CHARS_PER_WORD)
        duration_mins = round(word_target / WORDS_PER_MINUTE, 1)

        safety = self._topic_safety(topic or '')
        el_credits = self._elevenlabs_credits()
        heygen_credits = self._heygen_credits()

        go = (
            safety['safe']
            and (el_credits is None or el_credits >= char_estimate)
            and (heygen_credits is None or heygen_credits >= 1)
        )

        return {
            'go': go,
            'soul': soul_name,
            'format': format,
            'estimated_chars': char_estimate,
            'estimated_duration_mins': duration_mins,
            'topic_safety': safety,
            'elevenlabs_credits_remaining': el_credits,
            'heygen_credits_remaining': heygen_credits,
            'blockers': self._blockers(safety, el_credits, char_estimate, heygen_credits),
        }

    def _topic_safety(self, topic: str) -> dict:
        topic_lower = topic.lower()
        flags = [r for r in RISKY_TOPICS if r in topic_lower]
        return {'safe': len(flags) == 0, 'flags': flags}

    def _elevenlabs_credits(self) -> int | None:
        if not ELEVENLABS_KEY:
            return None
        try:
            r = requests.get('https://api.elevenlabs.io/v1/user', headers={'xi-api-key': ELEVENLABS_KEY}, timeout=8)
            if r.ok:
                sub = r.json().get('subscription', {})
                used = sub.get('character_count', 0)
                limit = sub.get('character_limit', 0)
                return max(0, limit - used)
        except Exception as e:
            log.warning(f"ElevenLabs credit check failed: {e}")
        return None

    def _heygen_credits(self) -> int | None:
        if not HEYGEN_KEY:
            return None
        try:
            r = requests.get('https://api.heygen.com/v2/user/remaining_quota',
                             headers={'X-Api-Key': HEYGEN_KEY}, timeout=8)
            if r.ok:
                return r.json().get('data', {}).get('remaining_quota', 0)
        except Exception as e:
            log.warning(f"HeyGen credit check failed: {e}")
        return None

    def _blockers(self, safety, el_credits, char_estimate, heygen_credits) -> list:
        out = []
        if not safety['safe']:
            out.append(f"Topic safety flags: {safety['flags']}")
        if el_credits is not None and el_credits < char_estimate:
            out.append(f"ElevenLabs insufficient: need {char_estimate}, have {el_credits}")
        if heygen_credits is not None and heygen_credits < 1:
            out.append("HeyGen: no credits remaining")
        return out
