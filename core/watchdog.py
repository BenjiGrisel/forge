"""
Watchdog — wraps every agent call with retry logic and auto-correction.
On failure: log → auto-correct → retry (up to 2x) → notify CEREBRO.
"""

import os
import time
import logging
import requests

log = logging.getLogger('forge.watchdog')
CEREBRO_URL = os.getenv('CEREBRO_WEBHOOK_URL', '')
MAX_RETRIES = 2


class Watchdog:
    def __init__(self, agent_name: str):
        self.agent = agent_name

    def run(self, fn, **kwargs):
        video_id = kwargs.get('video_id', 'unknown')
        last_error = None

        for attempt in range(1, MAX_RETRIES + 2):
            try:
                result = fn(**kwargs)
                if result.get('error'):
                    raise RuntimeError(result['error'])
                log.info(f"[{self.agent}] {video_id} ✓ attempt {attempt}")
                return result
            except Exception as e:
                last_error = str(e)
                log.warning(f"[{self.agent}] {video_id} attempt {attempt} failed: {e}")

                if attempt <= MAX_RETRIES:
                    correction = self._auto_correct(agent=self.agent, error=last_error, kwargs=kwargs)
                    if correction:
                        kwargs.update(correction)
                        log.info(f"[{self.agent}] auto-corrected: {correction}")
                    time.sleep(5 * attempt)

        self._notify_cerebro(video_id=video_id, agent=self.agent, error=last_error)
        return {'error': last_error, 'agent': self.agent, 'video_id': video_id}

    def _auto_correct(self, agent: str, error: str, kwargs: dict) -> dict | None:
        """Apply known corrections based on error patterns."""
        corrections = {
            'wordsmith': {
                'too long': lambda kw: {'max_words': int(kw.get('max_words', 800) * 0.85)},
                'rate limit': lambda kw: {'delay': kw.get('delay', 0) + 10},
            },
            'voice': {
                'quota': lambda kw: {'provider': 'kokoro'},
                'rate limit': lambda kw: {'delay': kw.get('delay', 0) + 15},
            },
            'visual': {
                'credit': lambda kw: {'provider': 'did'},
            },
        }
        rules = corrections.get(agent, {})
        for pattern, fix in rules.items():
            if pattern.lower() in error.lower():
                return fix(kwargs)
        return None

    def _notify_cerebro(self, video_id: str, agent: str, error: str):
        if not CEREBRO_URL:
            return
        try:
            requests.post(CEREBRO_URL, json={
                'event': 'forge_failure',
                'video_id': video_id,
                'agent': agent,
                'error': error,
            }, timeout=10)
        except Exception as e:
            log.error(f"Failed to notify CEREBRO: {e}")
