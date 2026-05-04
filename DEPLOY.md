# VPS Deployment Guide

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd korean-transcript

# 2. Copy and configure environment
cp .env.example .env
nano .env  # Edit OPENAI_API_KEY and CORS_ORIGINS

# 3. Start services
docker compose up -d

# 4. Verify
# Frontend: http://YOUR_VPS_IP:5173
# Backend Health: http://YOUR_VPS_IP:8000/api/health
```

## Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **YES** | Get from https://platform.openai.com/api-keys |
| `CORS_ORIGINS` | **YES** | Set to `http://YOUR_VPS_IP:5173` or your domain |

## Optional Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SONIOX_API_KEY` | empty | Dual-ASR mode for better accuracy |
| `DEEPSEEK_API_KEY` | empty | Alternative LLM provider |
| `GEMINI_API_KEY` | empty | Alternative LLM provider |
| `CLAUDE_API_KEY` | empty | Alternative LLM provider |

## CORS Configuration Examples

```bash
# For IP-based testing:
CORS_ORIGINS=http://123.45.67.89:5173

# For domain with www:
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# For subdomain:
CORS_ORIGINS=https://translator.yourdomain.com
```

## Troubleshooting

### "Chunk failed: Internal Server Error"
- Check backend logs: `docker logs korean-transcript-backend-1`
- Verify `OPENAI_API_KEY` is set correctly

### "Connection refused" from browser
- Check firewall: `sudo ufw allow 5173 && sudo ufw allow 8000`
- Verify containers running: `docker compose ps`

### Prompt files not found
- This was fixed in recent commits - ensure you have the latest code
- The app now searches multiple paths for Docker vs local layouts

## Updating After Code Changes

```bash
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```
