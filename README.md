# Korean Meeting Interpreter

Real-time Korean-to-multilingual meeting interpreter. Capture audio from your browser, get live transcription, reconstruction, and translation to Spanish, English, or Chinese. Upload meeting images for additional context.

## Features

- **Live Audio Recording**: Browser-based recording with automatic chunk uploads every 15 seconds
- **Dual ASR**: OpenAI Whisper + optional Soniox for improved accuracy
- **LLM Reconstruction**: AI reconstructs fragmented Korean into coherent sentences
- **Translation**: Real-time translation to ES / EN / ZH with terminology consistency
- **Live Photo Capture**: Snap photos during recording to add visual context to the conversation
- **Operational Summary**: Generate a structured meeting summary at the end
- **Docker Ready**: Single-command deployment via Docker Compose

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
| `SONIOX_API_KEY` | No | Soniox API key for dual-ASR mode |
| `DEEPSEEK_API_KEY` | No | Alternative LLM provider |
| `GEMINI_API_KEY` | No | Alternative LLM provider |
| `CLAUDE_API_KEY` | No | Alternative LLM provider |

All other variables have sensible defaults in `backend/app/config.py`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/session/start` | POST | Create new session |
| `/api/session/{id}/chunk` | POST | Upload audio chunk (WebM) |
| `/api/session/{id}/context/images` | POST | Upload image for context |
| `/api/session/{id}/transcript` | GET | Get current transcript |
| `/api/session/{id}/summary` | POST | Generate meeting summary |
| `/api/session/{id}/summary.md` | GET | Download summary as Markdown |
| `/api/session/{id}` | DELETE | End and cleanup session |

## Architecture

```
.
├── backend/
│   ├── app/
│   │   ├── asr/          # ASR clients (OpenAI Whisper, Soniox)
│   │   ├── audio/        # Audio chunking and overlap handling
│   │   ├── llm/          # LLM tasks: reconstruct, translate, summarize
│   │   ├── session/      # Session state management
│   │   └── main.py       # FastAPI application
│   ├── pyproject.toml
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── App.tsx       # React application (recording, transcript, photos)
│   │   ├── api.ts        # Backend API client
│   │   └── recorder.ts   # MediaRecorder audio chunking
│   ├── index.html
│   └── package.json
├── prompts/              # LLM prompt templates (Markdown)
├── Dockerfile            # Backend container
├── docker-compose.yml    # Full stack orchestration
└── .env.example          # Environment template
```

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic Settings
- **Frontend**: React 18, TypeScript, Vite
- **ASR**: OpenAI Whisper API, optional Soniox
- **LLM**: OpenAI GPT-5.4 series (configurable per task)
- **Audio**: ffmpeg (Docker), Web Audio API (browser)
- **Deployment**: Docker Compose, nginx reverse proxy

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

## VPS Deployment

See `DEPLOY.md` for detailed VPS deployment instructions including:
- CORS configuration for your domain
- Firewall setup
- Updating after code changes

## License

MIT License — see [LICENSE](LICENSE)

