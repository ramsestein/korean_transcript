# ko-meeting-interpreter

Real-time Korean-to-multilingual meeting interpreter with dual ASR (OpenAI + Soniox), LLM reconstruction, translation (ES/EN/ZH), and operational summary generation.

## Quick Start

### Prerequisites
- Python 3.11+ (backend & frontend)
- Docker & Docker Compose (optional)
- OpenAI API key
- Soniox API key
- ffmpeg (for audio processing)

### Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
OPENAI_API_KEY=sk-...
SONIOX_API_KEY=...
```

### Backend (Python)

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000` with API docs at `/docs`.

### Frontend (Streamlit)

```bash
cd frontend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\streamlit run app.py
```

Frontend runs at `http://localhost:8501`.

### Docker (Full Stack)

```bash
docker compose up -d --build
```

## Testing

```bash
# Backend unit tests
cd backend
.venv\Scripts\python -m pytest tests/unit -v

# Backend integration tests
.venv\Scripts\python -m pytest tests/integration -v

# Frontend tests
cd frontend
.venv\Scripts\python -m pytest test_app.py -v
```

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/session/start` | POST | Create new session |
| `/api/session/{id}/chunk` | POST | Upload audio chunk |
| `/api/session/{id}/context/images` | POST | Upload slide/image |
| `/api/session/{id}/transcript` | GET | Get current transcript |
| `/api/session/{id}/summary` | POST | Generate summary |
| `/api/session/{id}/summary.md` | GET | Download summary |
| `/api/session/{id}` | DELETE | End session |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── asr/          # ASR clients (OpenAI, Soniox)
│   │   ├── audio/        # Audio processing (chunking, overlap)
│   │   ├── llm/          # LLM providers & tasks
│   │   ├── session/      # Session management
│   │   └── main.py       # FastAPI app
│   └── tests/
├── frontend/
│   ├── app.py            # Streamlit application
│   └── test_app.py       # Streamlit tests
├── prompts/              # LLM prompt templates
├── test_data/            # Korean audio/text test samples
└── docker-compose.yml
```

## License

MIT
