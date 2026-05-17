# FORGE — AI Avatar Channel Automation Framework

> **Autonomous YouTube channel creation with AI avatars, voice cloning, and multi-agent orchestration.**

FORGE is a self-hosted, open-source pipeline that turns a soul file (character bible) + a topic into a fully produced, published YouTube video — without human intervention after initial setup.

Built on the [DMU (Digital Monkey Universe)](https://github.com/BenjiGrisel) architecture. Governed by the AEGIS constitutional layer. Orchestrated by CEREBRO. Executed by a swarm of six specialized agents.

---

## Architecture

```
GOVERNOR-PRIME (Dashboard) → CEREBRO (Slack/API) → n8n (Orchestrator) → Agent Swarm → YouTube
```

**Six agents. One pipeline.**

| Agent | Job |
|---|---|
| SCOUT | Research trending topics in your niche |
| WORDSMITH | Generate script using soul.md personality file |
| VOICE | Convert script to audio (ElevenLabs or local Kokoro) |
| VISUAL | Create avatar video (HeyGen or local LivePortrait) |
| EDITOR | Assemble final video with captions via FFmpeg |
| HERALD | Upload to YouTube, cross-post, update Notion, notify CEREBRO |

---

## Stack

**Cloud (Phase 1 — start fast):**
- Anthropic Claude API — script generation
- ElevenLabs — voice cloning
- HeyGen — talking-head avatar video
- YouTube Data API v3 — publishing
- Notion — content tracking

**Local/Self-Hosted (Phase 3 — zero per-video cost):**
- Kokoro-82M — TTS (CPU-friendly)
- LivePortrait + SadTalker — avatar animation
- Wan2.x / LTX-2 via ComfyUI — full video generation
- Whisper — captions
- FFmpeg — video assembly (always local)

**Orchestration (all self-hosted):**
- n8n — workflow engine
- Flask — agent API server
- Redis — job state
- Hetzner VPS — server (or any Linux VPS)

---

## Quick Start

```bash
git clone https://github.com/BenjiGrisel/forge
cd forge
cp .env.example .env        # fill in your keys
cp templates/TEMPLATE-SOUL.md souls/MY-PERSONA.md  # create your character
docker-compose up -d        # start the agent server + n8n
```

Then import `n8n/workflows/forge-pipeline.json` into your n8n instance.

Trigger a video:
```bash
curl -X POST http://localhost:5000/api/run \
  -H "Content-Type: application/json" \
  -d '{"soul": "MY-PERSONA", "channel_id": "UCxxxx", "topic_override": null}'
```

---

## What Goes in This Repo (Public)

- Pipeline engine and all agent scripts
- Soul.md template format + generic example personas
- n8n workflow blueprint (importable JSON)
- Docker setup for self-hosting
- Documentation

## What Stays Private (Never Commit)

- Your real soul.md files (your persona DNA)
- `.env` with actual API keys
- OAuth tokens / YouTube credentials
- HeyGen avatar IDs, ElevenLabs voice IDs
- Avatar images (your likeness)

---

## Requirements

- Python 3.11+
- Docker + Docker Compose
- n8n instance (self-hosted or cloud)
- FFmpeg installed on server
- API keys: Anthropic, ElevenLabs, HeyGen, YouTube (OAuth), Notion

---

## License

MIT — use it, fork it, build on it. If you make something cool, share it back.

---

*Built by [BenjiGrisel](https://github.com/BenjiGrisel) · Part of the Digital Monkey Universe*
