"""
SCOUT — Research agent.
Finds trending topics in the persona's niche using Reddit, YouTube, and web search.
Returns a scored topic with supporting context for WORDSMITH.
"""

import os
import logging
import requests
from core.soul import Soul
from core.registry import VideoRegistry

log = logging.getLogger('forge.scout')

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID', '')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', '')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'forge-scout/1.0')
SERPER_KEY = os.getenv('SERPER_API_KEY', '')


class Scout:
    def research(self, video_id: str, soul_name: str, topic_override: str = None) -> dict:
        soul = Soul(soul_name)
        reg = VideoRegistry()
        reg.update(video_id, status='scouting')

        if topic_override:
            topic = {'title': topic_override, 'score': 100, 'source': 'override', 'context': ''}
        else:
            candidates = []
            if soul.niche_keywords:
                candidates.extend(self._reddit_trends(soul.niche_keywords))
                if SERPER_KEY:
                    candidates.extend(self._web_trends(soul.niche_keywords))
            candidates.sort(key=lambda x: x['score'], reverse=True)
            topic = candidates[0] if candidates else self._fallback(soul)

        reg.update(video_id, topic=topic['title'], status='scouted')
        log.info(f"[scout] {video_id} → {topic['title']} (score: {topic['score']})")
        return {
            'video_id': video_id,
            'topic': topic['title'],
            'context': topic.get('context', ''),
            'source': topic.get('source', 'unknown'),
            'score': topic.get('score', 0),
        }

    def _reddit_trends(self, keywords: list) -> list:
        token = self._reddit_token()
        if not token:
            return []
        results = []
        subreddits = self._keywords_to_subreddits(keywords)
        headers = {'Authorization': f'Bearer {token}', 'User-Agent': REDDIT_USER_AGENT}
        for sub in subreddits[:3]:
            try:
                r = requests.get(
                    f'https://oauth.reddit.com/r/{sub}/hot.json?limit=10',
                    headers=headers, timeout=10
                )
                if not r.ok:
                    continue
                for post in r.json().get('data', {}).get('children', []):
                    p = post['data']
                    if p.get('score', 0) < 100:
                        continue
                    results.append({
                        'title': self._clean_title(p['title']),
                        'score': min(p['score'] // 10, 99),
                        'source': f'reddit/r/{sub}',
                        'context': p.get('selftext', '')[:500],
                    })
            except Exception as e:
                log.warning(f"Reddit fetch failed for r/{sub}: {e}")
        return results

    def _web_trends(self, keywords: list) -> list:
        query = ' OR '.join(keywords[:3]) + ' trending 2026'
        try:
            r = requests.post('https://google.serper.dev/search',
                              json={'q': query, 'num': 5},
                              headers={'X-API-KEY': SERPER_KEY}, timeout=10)
            if not r.ok:
                return []
            results = []
            for item in r.json().get('organic', []):
                results.append({
                    'title': item.get('title', ''),
                    'score': 50,
                    'source': 'web',
                    'context': item.get('snippet', ''),
                })
            return results
        except Exception as e:
            log.warning(f"Web search failed: {e}")
            return []

    def _reddit_token(self) -> str | None:
        if not REDDIT_CLIENT_ID:
            return None
        try:
            r = requests.post('https://www.reddit.com/api/v1/access_token',
                              data={'grant_type': 'client_credentials'},
                              auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
                              headers={'User-Agent': REDDIT_USER_AGENT}, timeout=8)
            return r.json().get('access_token') if r.ok else None
        except Exception:
            return None

    def _keywords_to_subreddits(self, keywords: list) -> list:
        mapping = {
            'legal': ['legaladvice', 'law', 'smallbusiness'],
            'business': ['entrepreneur', 'smallbusiness', 'startups'],
            'fitness': ['fitness', 'bodyweightfitness', 'over40fitness'],
            'veteran': ['Veterans', 'military', 'USMC'],
            'tactical': ['tacticalgear', 'preppers', 'CCW'],
            'coaching': ['personalfinance', 'selfimprovement', 'getdisciplined'],
        }
        subs = []
        for kw in keywords:
            for key, sub_list in mapping.items():
                if key in kw.lower():
                    subs.extend(sub_list)
        return list(dict.fromkeys(subs)) or ['entrepreneur']

    def _clean_title(self, title: str) -> str:
        import re
        title = re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()
        return title[:120]

    def _fallback(self, soul: Soul) -> dict:
        themes = soul.content_themes
        fallback = themes[0] if themes else 'What most people get wrong about success'
        return {'title': fallback, 'score': 1, 'source': 'fallback', 'context': ''}
