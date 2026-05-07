# Korean Meeting Interpreter

Real-time Korean-to-multilingual meeting interpreter. Capture audio from your browser, get live transcription, reconstruction, and translation to Spanish, English, or Chinese. Upload meeting images for additional context.

## Features

- **Live Audio Recording**: Browser-based recording with automatic chunk uploads every 15 seconds
- **Dual ASR**: OpenAI Whisper + optional Soniox for improved accuracy
- **LLM Reconstruction**: AI reconstructs fragmented Korean into coherent sentences
- **Translation**: Real-time translation to ES / EN / ZH with terminology consistency
- **Live Photo Capture**: Snap photos during recording to add visual context to the conversation
- **Operational Summary**: Generate a structured Markdown summary at the end of each session; filename includes timestamp and username (e.g. `summary_20260507_143022_ramses.md`)
- **Summary History**: Persistent logs volume stores all summaries per user; dedicated page to browse and download previous summaries
- **Docker Ready**: Single-command deployment via Docker Compose
- **Multi-User Auth**: Define users via environment variables (e.g., `USER1_USER=password`)
- **PWA Support**: Install as mobile app (Add to Home Screen)

## Quick Start (Docker Recommended)

```bash
# 1. Clone
git clone https://github.com/ramsestein/korean_transcript.git
cd korean_transcript

# 2. Configure environment
cp .env.example .env
# Edit .env: add OPENAI_API_KEY and CORS_ORIGINS

# 3. Launch
docker compose up -d --build

# 4. Open browser at http://localhost:5173
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **Yes** | OpenAI API key for transcription + LLM |
| `CORS_ORIGINS` | **Yes** | Your frontend URL (e.g. `http://yourdomain.com`) |
| `AUTH_ENABLED` | No | Set `true` to enable login protection |
| `*_USER` | If auth on | User credentials, e.g. `USER1_USER=password` creates user "user1" |
| `SONIOX_API_KEY` | No | Soniox API key for dual-ASR mode |
| `GOOGLE_API_KEY` | No | Google AI (Gemini) API key — used by default for reconstruct & translate |
| `CLAUDE_API_KEY` | No | Anthropic Claude API key (stub, not yet active) |
| `DATA_DIR` | No | Session data directory (default `/app/data`) |
| `LOGS_DIR` | No | Persistent summary logs directory (default `/app/logs`) |

All other variables have sensible defaults in `backend/app/config.py`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (public) |
| `/api/auth/status` | GET | Check if auth enabled + list users |
| `/api/auth/login` | POST | Login with username/password, returns token |
| `/api/auth/logout` | POST | Invalidate token |
| `/api/session/start` | POST | Create new session (requires auth) |
| `/api/session/{id}/chunk` | POST | Upload audio chunk (requires auth) |
| `/api/session/{id}/context/images` | POST | Upload image for context (requires auth) |
| `/api/session/{id}/transcript` | GET | Get current transcript (requires auth) |
| `/api/session/{id}/summary` | POST | Generate summary; saves to session + logs volume (requires auth) |
| `/api/session/{id}/summary.md` | GET | Download summary for current session (requires auth) |
| `/api/session/{id}` | DELETE | End and cleanup session (requires auth) |
| `/api/summaries` | GET | List all summaries belonging to the authenticated user (requires auth) |
| `/api/summaries/{filename}` | GET | Download a specific summary from the logs volume (requires auth) |

## Architecture

```
.
├── backend/
│   ├── app/
│   │   ├── asr/          # ASR clients (OpenAI Whisper, Soniox)
│   │   ├── audio/        # Audio chunking and overlap handling
│   │   ├── auth.py       # Multi-user authentication
│   │   ├── llm/          # LLM tasks: reconstruct, translate, summarize
│   │   │   └── providers/  # OpenAI, Google (Gemini), Anthropic (stub)
│   │   ├── output/       # Markdown writer, summary export (session + logs)
│   │   ├── session/      # Session state management
│   │   └── main.py       # FastAPI application
│   ├── pyproject.toml
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── App.tsx       # React application (setup / recording / done / summaries phases)
│   │   ├── api.ts        # Backend API client
│   │   ├── cookies.ts    # Cookie utilities
│   │   ├── Login.tsx     # Authentication UI
│   │   └── recorder.ts   # MediaRecorder audio chunking
│   ├── index.html
│   ├── public/
│   │   ├── manifest.json # PWA manifest
│   │   └── sw.js         # Service worker
│   └── package.json
├── prompts/              # LLM prompt templates
├── data/                 # Session data (mounted volume in Docker)
├── logs/                 # Persistent summary logs (mounted volume in Docker)
├── Dockerfile.web        # Combined frontend+backend for PaaS (nginx + uvicorn)
├── Dockerfile.backend    # Backend only (for docker-compose)
├── docker-compose.yml    # Local development
└── .env.example          # Environment template
```

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic Settings
- **Frontend**: React 18, TypeScript, Vite
- **ASR**: OpenAI Whisper API, optional Soniox
- **LLM**: OpenAI GPT-5.4 series + Google Gemini 2.5 Flash (configurable per task)
- **Audio**: ffmpeg (Docker), Web Audio API (browser)
- **Deployment**: Docker Compose, nginx reverse proxy; persistent `logs/` volume for summaries
- **Auth**: Multi-user with cookies (30-day session)
- **PWA**: Service worker, offline support, installable

## Development (Without Docker)

### Backend

```bash
cd backend
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Authentication Setup

Enable login protection by setting `AUTH_ENABLED=true` and defining users:

```bash
# In your .env file:
AUTH_ENABLED=true
USER1_USER=password123       # Creates user: user1
RAMSES_USER=mysecret         # Creates user: ramses
ADMIN_USER=adminpass         # Creates user: admin
```

- Users log in with username + password
- Session persisted via cookies (30 days)
- Login screen shows available users

## Mobile App (PWA)

The app can be installed on mobile devices:

**iOS (Safari):**
1. Open the app URL in Safari
2. Tap Share → "Add to Home Screen"
3. Open from home screen like a native app

**Android (Chrome):**
1. Open the app URL in Chrome
2. Tap Menu → "Add to Home screen"
3. Open from home screen like a native app

Features:
- Works offline (cached shell)
- No browser UI (fullscreen)
- Icon on home screen
- Splash screen with app name

## VPS Deployment

See `DEPLOY.md` for detailed VPS deployment instructions including:
- CORS configuration for your domain
- Authentication setup
- Firewall setup
- Updating after code changes

## License

MIT License — see [LICENSE](LICENSE)

