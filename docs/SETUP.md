# FORGE — Setup Guide

## Prerequisites

- Hetzner VPS (or any Linux server) with Docker + Docker Compose
- Existing n8n instance (n8n.digitalmonkey.io or your own)
- API accounts: Anthropic, ElevenLabs, HeyGen, Google Cloud (YouTube)
- Notion workspace

---

## Step 1 — Server Prep (Hetzner)

```bash
ssh root@YOUR_SERVER_IP

# Create forge directories (private — not in repo)
mkdir -p /opt/forge/media /opt/forge/souls /opt/forge/creds
mkdir -p /opt/forge/souls/assets   # put hero images here

# Clone the public repo
cd /opt
git clone https://github.com/BenjiGrisel/forge
cd forge

# Copy env file
cp .env.example .env
nano .env   # fill in all values
```

---

## Step 2 — API Setup (Do These Manually)

### HeyGen
1. Go to heygen.com → Sign up → Avatars → Photo Avatar
2. Upload each hero image → give each a name
3. Settings → API → Generate API Key
4. Note the Avatar IDs for each persona
5. Add to .env: `HEYGEN_API_KEY=...` and `HEYGEN_AVATAR_ID_{PERSONA_NAME}=...`

### ElevenLabs
1. Go to elevenlabs.io → Sign up (Starter plan, $5/mo)
2. Record 2–5 min of clean speech (no music, no background noise)
3. Voices → Add Voice → Professional Voice Clone → upload recording
4. Profile → API Keys → Create Key
5. Note Voice ID from voice settings
6. Add to .env: `ELEVENLABS_API_KEY=...` and `ELEVENLABS_VOICE_ID_DEFAULT=...`

### YouTube Data API v3
1. Go to console.cloud.google.com
2. Create project "forge" → Enable "YouTube Data API v3"
3. Credentials → OAuth 2.0 Client → Desktop App → Download JSON
4. Save to `/opt/forge/creds/client_secret.json`
5. Run: `python scripts/auth_youtube.py` (follow browser prompt)
6. Token saved to `/opt/forge/creds/youtube_token.json`
7. Add to .env: `YOUTUBE_CLIENT_ID=...` and `YOUTUBE_CLIENT_SECRET=...`

### Notion
1. notionhq.com → My Integrations → New Integration
2. Give it access to your workspace
3. Create two databases:
   - "FORGE Video Registry" — share with integration
   - "Content Calendar" — share with integration
4. Get Database IDs from the URL (the UUID after the workspace name)
5. Add to .env: `NOTION_API_KEY=...`, `NOTION_VIDEO_REGISTRY_DB=...`, `NOTION_CONTENT_CALENDAR_DB=...`

---

## Step 3 — Add Your Soul Files

```bash
# Copy your real soul.md files (keep private)
cp YOUR_PERSONA.md /opt/forge/souls/YOUR-PERSONA.md

# Copy hero images for LivePortrait (optional, Phase 3)
cp hero-image.png /opt/forge/souls/assets/YOUR-PERSONA-hero.png
```

Set up env vars for each persona:
```bash
# In .env:
ELEVENLABS_VOICE_ID_YOUR_PERSONA=eleven_labs_voice_id_here
HEYGEN_AVATAR_ID_YOUR_PERSONA=heygen_avatar_id_here
```

---

## Step 4 — Deploy

```bash
cd /opt/forge

# Build and start
docker-compose up -d --build

# Verify it's running
curl http://localhost:5001/health
# Expected: {"status": "ok", "service": "forge"}
```

---

## Step 5 — Import n8n Workflow

1. Open your n8n instance (n8n.digitalmonkey.io)
2. Workflows → New → Import from file
3. Upload `n8n/workflows/forge-pipeline.json`
4. Update these environment variables in n8n (Settings → Variables):
   - `FORGE_API_URL` = `http://forge-api:5001` (if n8n is on same Docker network) OR `http://YOUR_SERVER_IP:5001`
   - `FORGE_SECRET` = same value as in .env
   - `CEREBRO_WEBHOOK_URL` = your CEREBRO notification endpoint
5. Activate the workflow

---

## Step 6 — Test First Run

```bash
# Trigger manually via curl
curl -X POST https://n8n.digitalmonkey.io/webhook/forge-run \
  -H "Content-Type: application/json" \
  -H "X-Forge-Secret: YOUR_SECRET" \
  -d '{
    "soul": "YOUR-PERSONA",
    "channel_id": "UCxxxxxxxxxxxxxxxx",
    "format": "youtube_long",
    "topic_override": "What most business owners get wrong about contracts"
  }'
```

Monitor progress:
```bash
# Check video status
curl -H "X-Forge-Secret: YOUR_SECRET" \
  http://localhost:5001/api/status/VIDEO_ID_HERE
```

---

## Step 7 — Connect to CEREBRO (DMU)

Add to your CEREBRO Slack bot config:

```javascript
// In /opt/cerebro/cerebro-server.js — add forge command handler
app.command('/forge', async ({ command, ack, say }) => {
  await ack();
  const [soul, ...topicParts] = command.text.split(' ');
  const topic = topicParts.join(' ') || null;
  
  const resp = await fetch(`${process.env.N8N_WEBHOOK_BASE}/forge-run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Forge-Secret': process.env.FORGE_SECRET,
    },
    body: JSON.stringify({ soul, topic_override: topic, channel_id: process.env.YT_CHANNEL_DEFAULT }),
  });
  
  await say(`FORGE job triggered for ${soul}. ${topic ? `Topic: "${topic}"` : 'SCOUT choosing topic.'}`);
});
```

Then from Slack: `/forge GOVERNOR-PRIME What you need to know about LLC protection`

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Soul not found` | Check `/opt/forge/souls/PERSONA.md` exists |
| `YouTube token expired` | Run `python scripts/auth_youtube.py` again |
| `HeyGen credit` | Check balance at heygen.com, or switch `VISUAL_PROVIDER=did` |
| `ElevenLabs quota` | Check usage, switch `VOICE_PROVIDER=kokoro` for local TTS |
| `FFmpeg failed` | Check ffmpeg is installed: `ffmpeg -version` |
| n8n can't reach forge-api | Add forge to DMU Docker network: `docker network connect dmu-net forge-api` |
