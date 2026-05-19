"""
FORGE Agent API Server
Hetzner VPS orchestrator — exposes all agents as HTTP endpoints for n8n.
"""

import os
import logging
from flask import Flask, request, jsonify
from functools import wraps

from core.registry import VideoRegistry
from core.preflight import Preflight
from core.watchdog import Watchdog
from core.agents.scout import Scout
from core.agents.wordsmith import Wordsmith
from core.agents.voice import VoiceAgent
from core.agents.visual import VisualAgent
from core.agents.editor import Editor
from core.agents.herald import Herald

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
log = logging.getLogger('forge')

app = Flask(__name__)
FORGE_SECRET = os.getenv('FORGE_SECRET', '')


def require_secret(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = request.headers.get('X-Forge-Secret', '')
        if FORGE_SECRET and secret != FORGE_SECRET:
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'forge'})


@app.route('/api/preflight', methods=['POST'])
@require_secret
def preflight():
    """Pre-flight check: estimate costs, verify credits, topic safety."""
    data = request.json
    result = Preflight().run(
        soul_name=data.get('soul'),
        topic=data.get('topic'),
        format=data.get('format', 'youtube_long')
    )
    return jsonify(result)


@app.route('/api/run', methods=['POST'])
@require_secret
def run_pipeline():
    """Trigger a full pipeline run. Returns video_id for polling."""
    data = request.json
    soul_name = data.get('soul')
    channel_id = data.get('channel_id')
    topic_override = data.get('topic_override')
    fmt = data.get('format', 'youtube_long')

    reg = VideoRegistry()
    video_id = reg.init(soul_name=soul_name, channel_id=channel_id, format=fmt)
    log.info(f"Pipeline started: {video_id}")
    return jsonify({'video_id': video_id, 'status': 'queued'})


@app.route('/api/scout', methods=['POST'])
@require_secret
def scout():
    data = request.json
    wd = Watchdog('scout')
    result = wd.run(Scout().research, video_id=data['video_id'], soul_name=data['soul'],
                    topic_override=data.get('topic_override'))
    return jsonify(result)


@app.route('/api/wordsmith', methods=['POST'])
@require_secret
def wordsmith():
    data = request.json
    wd = Watchdog('wordsmith')
    result = wd.run(Wordsmith().generate, video_id=data['video_id'], soul_name=data['soul'],
                    topic=data['topic'], format=data.get('format', 'youtube_long'))
    return jsonify(result)


@app.route('/api/voice', methods=['POST'])
@require_secret
def voice():
    data = request.json
    wd = Watchdog('voice')
    result = wd.run(VoiceAgent().generate, video_id=data['video_id'], soul_name=data['soul'],
                    script=data['script'])
    return jsonify(result)


@app.route('/api/visual', methods=['POST'])
@require_secret
def visual():
    data = request.json
    wd = Watchdog('visual')
    result = wd.run(VisualAgent().generate, video_id=data['video_id'], soul_name=data['soul'],
                    audio_path=data['audio_path'], format=data.get('format', 'youtube_long'))
    return jsonify(result)


@app.route('/api/visual/status', methods=['GET'])
@require_secret
def visual_status():
    """Poll HeyGen/provider for video completion."""
    video_id = request.args.get('video_id')
    provider_job_id = request.args.get('provider_job_id')
    result = VisualAgent().poll_status(provider_job_id=provider_job_id)
    return jsonify(result)


@app.route('/api/editor', methods=['POST'])
@require_secret
def editor():
    data = request.json
    wd = Watchdog('editor')
    result = wd.run(Editor().assemble, video_id=data['video_id'], soul_name=data['soul'],
                    video_path=data.get('video_path'), audio_path=data['audio_path'],
                    script=data['script'], format=data.get('format', 'youtube_long'),
                    video_url=data.get('video_url'))
    return jsonify(result)


@app.route('/api/herald', methods=['POST'])
@require_secret
def herald():
    data = request.json
    wd = Watchdog('herald')
    result = wd.run(Herald().publish, video_id=data['video_id'], soul_name=data['soul'],
                    final_path=data['final_path'], thumbnail_path=data.get('thumbnail_path'),
                    script=data['script'], channel_id=data['channel_id'])
    return jsonify(result)


@app.route('/api/status/<video_id>', methods=['GET'])
@require_secret
def status(video_id):
    reg = VideoRegistry()
    record = reg.get(video_id)
    if not record:
        return jsonify({'error': 'not found'}), 404
    return jsonify(record)


if __name__ == '__main__':
    port = int(os.getenv('FORGE_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
