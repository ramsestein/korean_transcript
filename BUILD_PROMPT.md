# ko-meeting-interpreter — Autonomous Build Prompt

You are working in agentic mode inside VS Code. Your job is to build the **ko-meeting-interpreter** project end-to-end — code, tests, Docker, README, working live integration — and not stop until the Final Acceptance Checklist (§13) is 100% green. The repository is empty (or near-empty); you create everything.

The user is a physician at Hospital Clínic de Barcelona running this for his own meetings with Korean collaborators. There are 1–2 trusted users. No multi-user concerns. No patient data will ever flow through it. Quality and reliability matter; ceremony does not.

> **This document is committed to the repository as `BUILD_PROMPT.md` at the root.** It is your canonical spec. You re-read it at the start of every work session, before every phase transition, and before declaring done. Alongside it you maintain `BUILD_PROGRESS.md` (see §1.1) as your living state file so that any future Claude session — including a resumed one after interruption — can pick up exactly where you left off without losing track of what is complete and what is pending.

---

## 1. Working Mode (read this first, then re-read before every commit)

**You operate autonomously.** Implement → verify → fix → continue. Do not pause to ask the user unless you are blocked by something only they can resolve (e.g., an API key returning 401 because it is invalid, a port permanently bound by another process you cannot kill).

**Verification is non-negotiable.** After every meaningful change you run the relevant verification command (test suite, `docker compose up`, `curl` against an endpoint, `npm run build`, `pytest -m unit`, etc.). A red bar stops forward progress: you debug and fix before moving on.

**You write real code.** No placeholders, no `# TODO: implement`, no `pass`-only functions, no mock implementations shipped as if they were real. If you cannot implement something now, you stop and tell the user — you do not paper over it.

**You verify against live APIs at least once per integration.** OpenAI, Soniox, and the vision endpoint must each be hit with a real request during your run, with the keys from `.env`. You confirm the response shape matches your code. Mocked tests are for CI; live verification is for you.

**Decisions are locked.** §3 is final. Do not "improve" the model choice, change the language list, switch to WebSockets, add authentication, or restructure the repo. If you find a real architectural conflict (something in this spec is internally contradictory), surface it explicitly and ask — don't silently deviate.

**Definition of done.** §13. You stop when every item there is checked. Not before.

**Resume protocol.** If you are starting a new conversation on a repo that already has files, your first three actions, in order, are:
1. `view BUILD_PROMPT.md` — re-anchor to the spec.
2. `view BUILD_PROGRESS.md` — read your own previous state.
3. Continue from the `Next action` line in `BUILD_PROGRESS.md`. Do not restart from Phase 1.

---

## 1.1 Persistent State: BUILD_PROGRESS.md

You maintain `BUILD_PROGRESS.md` at the repo root as your **living state file**. After every meaningful milestone — a test suite turning green, an endpoint wired up, a phase completing, a live API verified — you update it and commit it. The user reads this file to check progress without interrupting you.

**Update cadence:** at minimum, after every Phase Verification Gate (§10), and after each item in §13 is completed. Smaller updates (e.g. after a long debugging session that resolved a blocker) are encouraged.

**Format (use this template verbatim, fill it in, keep it updated):**

```markdown
# Build Progress

_Last updated: <ISO-8601 timestamp UTC>_
_Current phase: <1–5 or "Acceptance">_
_Next action: <one concrete sentence describing exactly what you will do next>_

## Phase status
- [ ] Phase 1 — repo skeleton, Docker, session start endpoint, frontend skeleton, chunk upload plumbing
- [ ] Phase 2 — ASR clients, parallel ASR, agreement scoring, reconstruction LLM, translation LLM (es/en/zh)
- [ ] Phase 3 — image context upload, vision LLM, context integration into reconstruction prompts
- [ ] Phase 4 — retroactive correction, operational summary, summary.md download, 24h cleanup task
- [ ] Phase 5 — full test suite green, prompt eval gate (mocked judges) passing

## §13 Acceptance Checklist Status
<mirror every checkbox from §13 here, tick as completed>

## Verification log (newest first)
- <ISO timestamp> — <command run> → <result, truncated>
- ...

## Open issues / deferred
- <anything noted but not yet addressed, with reason>

## Deviations from spec
- <any place you intentionally diverged from BUILD_PROMPT.md, with justification>
```

**Rules for BUILD_PROGRESS.md:**
- Only check a box when the work is genuinely done and verified, not when you've started it.
- The `Next action` line must always be concrete and executable. Bad: "continue Phase 2." Good: "implement `asr/soniox_asr.py` async client and write 3 unit tests for token-level parsing."
- The Verification log accumulates; do not delete entries. It is the audit trail.
- If you are about to step away from a long-running task (you've hit a context limit, a verification needs human attention, etc.), make sure `Next action` is precise enough that a fresh Claude session can resume without re-reading the whole codebase.
- Commit `BUILD_PROGRESS.md` whenever you update it. Use commit messages like `progress: phase 2 complete, all integration tests green`.

---

## 2. Project Mission

A mobile-first web app that helps the user follow Korean meetings:

1. Records Korean speech from the phone's microphone in 15-second chunks.
2. Uploads each chunk to a backend over HTTP (not WebSockets).
3. Transcribes each chunk in parallel through OpenAI's ASR and Soniox.
4. Reconciles the two transcripts with an LLM into the most plausible Korean text, using meeting context, image context, and previous segments.
5. Translates the reconstructed Korean into the selected target language (Spanish, English, or Chinese).
6. Allows retroactive correction of the previous 2 segments when new context arrives.
7. At the end of the meeting, generates an operational `summary.md` the user can download.
8. Auto-deletes session data after 24 hours.

The frontend is **entirely in English**. Mobile-first. No fancy UI — function over form.

---

## 3. Locked Decisions (do not negotiate)

### 3.1 Languages
- **Source:** Korean only (`ko`).
- **Targets:** `es`, `en`, `zh` (Spanish, English, Simplified Chinese). All three must be selectable in the UI and have their own translation prompt file.

### 3.2 ASR providers (both run in parallel for every chunk)
- **OpenAI ASR:** model `gpt-4o-transcribe`. No diarization (it doesn't support it). Use the `/v1/audio/transcriptions` endpoint.
- **Soniox:** model `stt-async-v4`. Diarization **enabled** (`enable_speaker_diarization: true`). Language hint: `["ko"]`. Use Soniox async API on each chunk.

### 3.3 LLM stack (all OpenAI for simplicity)
- **Reconstruction (KO from two ASR hypotheses):** `gpt-5.4-mini`
- **Translation (KO → es/en/zh, all three):** `gpt-5.4-mini`
- **Vision (image context extraction):** `gpt-5.4-nano`
- **Operational summary:** `gpt-5.4-mini`
- **Prompt-eval judge A:** `gpt-5.4` (full model — diversity vs mini)
- **Prompt-eval judge B:** `gpt-5.4-mini`

All LLM calls go through the OpenAI Chat Completions API or Responses API, JSON mode where supported. The architecture must be **provider-agnostic** (see §6.4) even though every model in the initial stack is OpenAI — this is so the user can swap a task to Gemini/Claude later by changing `.env` only.

### 3.4 Diarization
Comes from Soniox tokens (each token has a `speaker` field when diarization is enabled). The reconstruction prompt receives the Soniox transcript as `Speaker 1: ... Speaker 2: ...` and the OpenAI transcript as plain text. The LLM reconciles.

### 3.5 Overlap (server-side simulation)
- Client sends **non-overlapping** 15-second chunks (`MediaRecorder` with `timeslice = 15000`).
- Server keeps a rolling buffer of the **last 2 seconds of audio** of the previous chunk per session.
- Before sending to ASR, server prepends those 2 seconds to the new chunk: ASR sees a 17 s clip.
- After ASR, server uses **token timestamps** to drop the prefix that corresponds to the prepended audio (timestamp < 2.0 s relative to the augmented clip).
- The "clean" transcript (post-prefix-drop) is what flows downstream. The dropped prefix is logged for debugging only.

### 3.6 Storage & retention
- Local filesystem under `DATA_DIR` (default `/app/data` in container).
- One folder per session: `{DATA_DIR}/{session_id}/` with subfolders `audio_raw/`, `audio_processed/`, `asr/`, `llm/`, `images/`, plus `manifest.json` and (after generation) `summary.md`.
- Cleanup task: every hour, scan and `rm -rf` any session folder whose `manifest.json.created_at` is older than `SESSION_TTL_HOURS` (default 24).

### 3.7 Out of scope (do not implement)
Local ASR/Whisper, CUDA, Clova, authentication beyond optional shared-secret header, billing/cost tracking, multi-format export (only `summary.md`), WebSocket streaming, replay/debug mode.

---

## 4. Repository Structure

```
ko-meeting-interpreter/
├─ README.md
├─ BUILD_PROMPT.md              # this document (the spec); committed
├─ BUILD_PROGRESS.md            # living state file you maintain (§1.1); committed
├─ BUILD_REPORT.md              # final report at end (§15); committed
├─ .env.example
├─ .env                         # gitignored, created by user; you read from it
├─ .gitignore
├─ docker-compose.yml
├─ Dockerfile                   # backend
├─ Makefile                     # convenience targets (build, up, down, test, lint)
├─ backend/
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py                # FastAPI app, routes, startup hooks
│  │  ├─ config.py              # Pydantic Settings, loads from .env
│  │  ├─ schemas.py             # All Pydantic models
│  │  ├─ deps.py                # FastAPI dependencies (session, settings)
│  │  ├─ audio/
│  │  │  ├─ __init__.py
│  │  │  ├─ convert.py          # ffmpeg wrappers (webm/opus/m4a → wav 16k mono)
│  │  │  ├─ chunking.py         # overlap-prepend + duration helpers
│  │  │  └─ overlap.py          # post-ASR overlap-drop using timestamps
│  │  ├─ asr/
│  │  │  ├─ __init__.py
│  │  │  ├─ openai_asr.py       # async client for /v1/audio/transcriptions
│  │  │  ├─ soniox_asr.py       # async client for Soniox async REST API
│  │  │  ├─ parallel_asr.py     # asyncio.gather both, return both results
│  │  │  └─ agreement.py        # lexical_similarity, length_ratio, hint
│  │  ├─ llm/
│  │  │  ├─ __init__.py
│  │  │  ├─ client.py           # provider-agnostic factory
│  │  │  ├─ providers/
│  │  │  │  ├─ __init__.py
│  │  │  │  ├─ base.py          # LLMProvider abstract
│  │  │  │  ├─ openai_provider.py
│  │  │  │  ├─ anthropic_provider.py   # stub for future
│  │  │  │  └─ google_provider.py      # stub for future
│  │  │  ├─ reconstruct.py      # uses LLM_*_RECONSTRUCT
│  │  │  ├─ translate.py        # uses LLM_*_TRANSLATE
│  │  │  ├─ image_context.py    # uses LLM_*_VISION
│  │  │  ├─ summarize.py        # uses LLM_*_SUMMARY
│  │  │  └─ judge.py            # used by prompt eval only
│  │  ├─ session/
│  │  │  ├─ __init__.py
│  │  │  ├─ manager.py          # create/get/delete session, manifest
│  │  │  ├─ store.py            # filesystem ops
│  │  │  ├─ context_window.py   # build LLM context from previous N segments
│  │  │  └─ cleanup.py          # background TTL task
│  │  └─ output/
│  │     ├─ __init__.py
│  │     ├─ markdown.py         # safe markdown writer
│  │     └─ summary_export.py   # summary.md generation orchestration
│  └─ prompts/                  # symlink or copy of /prompts at runtime
├─ prompts/
│  ├─ reconstruct_ko.md
│  ├─ translate_es.md
│  ├─ translate_en.md
│  ├─ translate_zh.md
│  ├─ image_context.md
│  ├─ operational_summary.md
│  └─ judge_prompt_quality.md
├─ frontend/
│  ├─ Dockerfile
│  ├─ package.json
│  ├─ tsconfig.json
│  ├─ vite.config.ts
│  ├─ index.html
│  └─ src/
│     ├─ main.tsx
│     ├─ App.tsx
│     ├─ recorder.ts            # MediaRecorder wrapper, 15s timeslice
│     ├─ api.ts                 # fetch wrappers
│     ├─ types.ts
│     ├─ styles.css             # mobile-first
│     └─ components/
│        ├─ LanguageSelector.tsx
│        ├─ ContextPromptBox.tsx
│        ├─ ImageUploader.tsx
│        ├─ RecorderControls.tsx
│        ├─ ChunkStatus.tsx
│        ├─ TranscriptView.tsx
│        └─ SummaryButton.tsx
└─ tests/
   ├─ conftest.py               # markers, shared fixtures, test session dir
   ├─ unit/
   │  ├─ test_schemas.py
   │  ├─ test_agreement.py
   │  ├─ test_overlap.py
   │  ├─ test_context_window.py
   │  ├─ test_markdown.py
   │  ├─ test_cleanup.py
   │  ├─ test_image_context_schema.py
   │  ├─ test_llm_json_parsing.py
   │  └─ test_fallbacks.py
   ├─ integration/
   │  ├─ test_session_lifecycle.py
   │  ├─ test_chunk_pipeline.py
   │  ├─ test_parallel_asr.py
   │  ├─ test_retroactive_correction.py
   │  ├─ test_image_endpoint.py
   │  └─ test_summary_endpoint.py
   ├─ e2e/
   │  └─ test_full_session.spec.ts   # Playwright
   ├─ prompt_eval/
   │  ├─ seeds/
   │  │  ├─ 01_academic_ko_es.json
   │  │  ├─ 02_medical_ko_es.json
   │  │  ├─ 03_academic_ko_zh.json
   │  │  ├─ 04_academic_ko_en.json
   │  │  ├─ 05_asr_disagreement_terminology.json
   │  │  ├─ 06_low_confidence.json
   │  │  └─ 07_summary_with_action_items.json
   │  ├─ rubrics/
   │  │  ├─ reconstruct.md
   │  │  ├─ translate.md
   │  │  └─ summary.md
   │  ├─ run_eval.py
   │  └─ test_prompt_quality.py
   └─ fixtures/
      ├─ audio_chunk_15s.wav         # sample real or synthesized
      ├─ asr_responses/
      │  ├─ openai_chunk1.json
      │  └─ soniox_chunk1.json
      └─ images/
         └─ sample_slide.png
```

---

## 5. Environment Variables

### 5.1 `.env.example` (committed)

```dotenv
# === OpenAI ===
OPENAI_API_KEY=
OPENAI_ASR_MODEL=gpt-4o-transcribe

# === Soniox ===
SONIOX_API_KEY=
SONIOX_MODEL=stt-async-v4

# === LLM stack (provider-agnostic; current stack is all OpenAI) ===
LLM_PROVIDER_RECONSTRUCT=openai
LLM_MODEL_RECONSTRUCT=gpt-5.4-mini

LLM_PROVIDER_TRANSLATE=openai
LLM_MODEL_TRANSLATE=gpt-5.4-mini

LLM_PROVIDER_VISION=openai
LLM_MODEL_VISION=gpt-5.4-nano

LLM_PROVIDER_SUMMARY=openai
LLM_MODEL_SUMMARY=gpt-5.4-mini

LLM_PROVIDER_JUDGE_A=openai
LLM_MODEL_JUDGE_A=gpt-5.4

LLM_PROVIDER_JUDGE_B=openai
LLM_MODEL_JUDGE_B=gpt-5.4-mini

# Optional alternative provider keys (only needed if you switch a task above)
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# === Pipeline ===
DEFAULT_CHUNK_SECONDS=15
DEFAULT_OVERLAP_SECONDS=2
RETROACTIVE_CORRECTION_SEGMENTS=2
CONTEXT_WINDOW_SEGMENTS=6           # how many previous segments to include in LLM context
SESSION_TTL_HOURS=24
DATA_DIR=/app/data
MAX_IMAGE_MB=10

# === Eval ===
MAX_PROMPT_REWRITE_ATTEMPTS=3

# === Server ===
BACKEND_PORT=8000
FRONTEND_PORT=5173
CORS_ORIGINS=http://localhost:5173
```

### 5.2 `.env` (gitignored)
Same keys, real values. The user has already populated `OPENAI_API_KEY` and `SONIOX_API_KEY` in their `.env`. You read from `.env` at runtime. Add `.env` to `.gitignore`.

---

## 6. Backend Contract

### 6.1 Endpoints

All endpoints return JSON unless noted. All errors use `{"error": "...", "detail": "..."}` with HTTP status.

#### `POST /api/session/start`
Request:
```json
{
  "target_language": "es" | "en" | "zh",
  "meeting_prompt": "string",
  "chunk_seconds": 15,
  "overlap_seconds": 2
}
```
Response: `{"session_id": "string"}`

Behavior: validates `target_language ∈ {es,en,zh}`, creates session folder, writes `manifest.json`.

#### `POST /api/session/{session_id}/chunk`
Multipart fields:
- `audio` (file, the 15 s chunk; webm/opus/m4a/wav accepted)
- `chunk_index` (int)
- `local_start_time` (float, seconds since session start, client-side)
- `local_end_time` (float)

Behavior (all of this in one request):
1. Persist raw audio to `audio_raw/{chunk_index}.{ext}`.
2. Convert to wav 16 kHz mono → `audio_processed/{chunk_index}.wav`.
3. Build augmented clip: prepend last 2 s of `audio_processed/{chunk_index-1}.wav` if exists.
4. Send augmented clip to OpenAI ASR and Soniox **in parallel** (`asyncio.gather`).
5. Drop prefix tokens with `t < overlap_seconds` from each transcript.
6. Compute agreement metrics (§6.3).
7. Build LLM context window (last `CONTEXT_WINDOW_SEGMENTS` reconstructed Korean + last translations + meeting prompt + image-derived context).
8. Call reconstruction LLM → reconstructed Korean + confidence + uncertainties.
9. Call translation LLM → translated text in target language.
10. Save segment to `llm/segment_{chunk_index}.json`.
11. **Retroactive correction:** re-run reconstruction + translation for the previous `RETROACTIVE_CORRECTION_SEGMENTS` segments **only if** new context plausibly affects them. Heuristic: re-run if the new segment introduces a named entity or technical term not seen before. Mark revised segments `revision_status: "revised"`. Segments older than `RETROACTIVE_CORRECTION_SEGMENTS` are marked `"final"`.
12. Return all segments touched (the new one + any revised).

Response:
```json
{
  "chunk_index": 1,
  "status": "processed",
  "segments": [
    {
      "segment_id": "string",
      "time_start": 0.0,
      "time_end": 15.0,
      "openai_asr_ko": "string",
      "soniox_asr_ko": "string",
      "soniox_speakers": [{"speaker": "1", "text": "..."}, ...],
      "reconstructed_ko": "string",
      "translated_text": "string",
      "target_language": "es",
      "confidence": "high" | "medium" | "low",
      "uncertainties": [],
      "agreement": {
        "lexical_similarity": 0.0,
        "length_ratio": 1.0,
        "confidence_hint": "high" | "medium" | "low"
      },
      "revision_status": "draft" | "revised" | "final"
    }
  ]
}
```

If one ASR fails, continue with the other and log the failure in the segment (`openai_asr_error` or `soniox_asr_error`). If both fail, return HTTP 502.

#### `POST /api/session/{session_id}/context/images`
Multipart: one or more image files (max `MAX_IMAGE_MB` each, png/jpg/webp).
Behavior: save → call vision LLM → store `images/{img_id}.json` with extracted structured context. Future chunk processing automatically includes all image contexts.
Response: `{"image_ids": [...], "extracted": [...]}`

#### `GET /api/session/{session_id}/transcript`
Returns full session: target language, meeting prompt, image contexts, all segments in order.

#### `POST /api/session/{session_id}/summary`
Behavior: aggregate full reconstructed Korean transcript + full translated transcript + meeting prompt + image contexts → call summary LLM → write `summary.md` → return URL.
Response: `{"status": "generated", "download_url": "/api/session/{session_id}/summary.md"}`

#### `GET /api/session/{session_id}/summary.md`
Returns the file with `Content-Type: text/markdown; charset=utf-8` and `Content-Disposition: attachment; filename="summary.md"`.

#### `DELETE /api/session/{session_id}`
Removes the session folder. Idempotent.

#### `GET /api/health`
Returns `{"status": "ok"}` (used by Docker healthcheck and frontend startup).

### 6.2 Background tasks
On FastAPI startup, schedule an asyncio task that runs every hour and removes session folders whose `manifest.json.created_at` is older than `SESSION_TTL_HOURS`. Use `asyncio.create_task` — no Redis, no RQ.

### 6.3 Agreement scoring (`asr/agreement.py`)
```python
def lexical_similarity(a: str, b: str) -> float:
    # rapidfuzz.fuzz.token_set_ratio / 100, after normalization (NFC, lower, strip punct)
def length_ratio(a: str, b: str) -> float:
    # min(len)/max(len) on whitespace-tokenized sequences; 1.0 if both empty
def confidence_hint(lex: float, lr: float) -> str:
    if lex >= 0.85 and lr >= 0.80: return "high"
    if lex >= 0.60: return "medium"
    return "low"
```
Edge cases: both empty → `length_ratio=1.0, lex=1.0, hint="high"`. One empty → `length_ratio=0.0, lex=0.0, hint="low"`.

### 6.4 LLM client architecture (`llm/client.py` + `llm/providers/`)

```python
# llm/providers/base.py
class LLMProvider(Protocol):
    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        images: list[bytes] | None = None,
        max_tokens: int = 2048,
    ) -> dict: ...
```

`llm/client.py` exposes:
```python
def get_provider(task: Literal["reconstruct","translate","vision","summary","judge_a","judge_b"]) -> tuple[LLMProvider, str]:
    """Returns (provider_instance, model_name) by reading LLM_PROVIDER_<TASK> and LLM_MODEL_<TASK>."""
```

Initial implementation: only `OpenAIProvider` is fully implemented. `AnthropicProvider` and `GoogleProvider` raise `NotImplementedError` with a clear message. Tests verify both routes (mock the provider, not the HTTP client).

OpenAI provider uses the `openai` Python SDK ≥ latest, async client, `response_format={"type": "json_object"}` for JSON tasks. For vision, pass images as base64 data URLs in the user message content array.

### 6.5 Retroactive correction logic
When processing chunk N, after producing its segment, examine the segment for **new terminology**: any Korean noun phrase or transliterated foreign word not present in segments 0..N-1 or in image contexts. If at least one new term appears, re-run reconstruction (only) for segments N-1 and N-2 with the updated context window. If reconstruction changes (string diff > 5% chars), also re-run translation and update. Keep an audit field `revision_history` with timestamps and reasons. Limit to `RETROACTIVE_CORRECTION_SEGMENTS` segments back. Beyond that → `revision_status: "final"`.

This is intentionally lightweight; do not turn it into a research project.

---

## 7. Frontend Contract

Stack: React 18 + Vite + TypeScript. Plain CSS (no Tailwind required; if you use it, pin a version). State via `useState`/`useReducer`; no Redux. Mobile-first: design for 375 px width primary, scale up.

### 7.1 Initial screen
- Header: "Korean Meeting Interpreter"
- Target language selector (segmented control or `<select>`): Spanish / English / Chinese
- Meeting context textarea (label: "Meeting context", placeholder: "Describe the meeting topic, people, institution, terminology, goals, etc.")
- Image upload (label: "Upload contextual images", multi-file)
- "Start recording" button (disabled until target language chosen)

### 7.2 Recording screen
- Big "Stop recording" button
- Live status: chunk index currently uploading, processing state per chunk
- Chunk status list: each chunk shows one of `recorded → uploaded → transcribed → reconstructed → translated → done` (or `error` with message)
- Transcript view: scrollable list of segments. Each segment shows reconstructed Korean (smaller) + translation (larger), confidence badge, uncertainties (collapsible), and revision status (`draft` italic, `revised` highlighted, `final` plain)

### 7.3 Post-recording
- "Generate operational summary" button (calls summary endpoint, shows spinner)
- "Download summary.md" button (visible after generation; triggers download)
- "End session" button (calls DELETE)

### 7.4 Recording behavior (`recorder.ts`)
- `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1, sampleRate: 16000 } })`
- `MediaRecorder` with `timeslice = chunk_seconds * 1000` (15000)
- On each `dataavailable`: build `FormData`, POST to `/api/session/{id}/chunk` (don't block recording on response)
- Maintain a queue; if a chunk upload fails, retry once with backoff, then mark error and continue
- Handle iOS Safari: select MIME type via `MediaRecorder.isTypeSupported()` (prefer `audio/webm;codecs=opus`, fallback `audio/mp4`)
- Emit progress events for the UI

### 7.5 Mobile-first guidance
- Tap targets ≥ 44 px
- No hover-only interactions
- Large monospace-ish font for Korean and CJK to render well across devices

---

## 8. Prompt Files (verbatim — write these exact contents)

### `prompts/reconstruct_ko.md`
```
You are reconstructing Korean speech from two ASR systems whose outputs are noisy and disagree in places.

INPUTS provided in the user message:
- openai_asr_ko: plain Korean transcript from OpenAI's gpt-4o-transcribe
- soniox_asr_ko: Korean transcript from Soniox with speaker labels (e.g. "Speaker 1: ...")
- agreement: { lexical_similarity, length_ratio, confidence_hint }
- previous_segments: last reconstructed Korean segments in order
- previous_translations: last translated segments in target language
- meeting_prompt: free-text context written by the user
- image_context: structured extractions from uploaded images (terms, entities, agenda)

RULES:
- Do not invent content. Use context only to disambiguate, never to add unsupported facts.
- If agreement.confidence_hint == "high": stay close to whichever ASR text is fluent. Differences are likely small.
- If "medium": reconcile differences using meeting_prompt, image_context, and previous_segments. Prefer the variant matching established terminology.
- If "low": choose the most plausible interpretation overall and explicitly mark uncertainty in `uncertainties`.
- Preserve names, institutions, dataset names, technical terms, drug names, and numbers verbatim. Do not translate them inside the Korean output.
- Korean academic and medical speech often code-switches into English. Keep English terms as English where the speaker said them.
- Use Soniox speaker labels to keep speaker turns coherent in the reconstructed output (you may inline "[Speaker 1]" markers; not required).
- Output VALID JSON only. No prose, no markdown fences.

OUTPUT JSON SCHEMA:
{
  "reconstructed_ko": "string",
  "confidence": "high" | "medium" | "low",
  "uncertainties": ["string", ...],
  "terminology": ["string", ...]
}
```

### `prompts/translate_es.md`
```
You translate reconstructed Korean meeting speech into formal, natural Spanish.

INPUTS:
- reconstructed_ko: the Korean text to translate
- meeting_prompt: free-text context
- image_context: structured term extractions
- previous_translations: last few Spanish translations for tonal/terminological consistency

RULES:
- Formal, natural Spanish suitable for a hospital/academic setting.
- Preserve technical meaning. Do NOT simplify medical, academic, or engineering terms.
- Names, institutions, datasets, acronyms, drug names, model names: keep unchanged unless a standard Spanish equivalent exists (e.g. "Universidad de Seúl" is fine for "서울대학교"; but "MIMIC-IV" stays "MIMIC-IV").
- Numbers: keep numerals; convert units only if doing so does not change meaning.
- Code-switched English terms: usually keep in English, italicize mentally.
- If the source contains an uncertainty marker, surface it in the `uncertainties` array.
- Output VALID JSON only.

OUTPUT JSON:
{
  "translated_text": "string",
  "confidence": "high" | "medium" | "low",
  "uncertainties": ["string", ...]
}
```

### `prompts/translate_en.md`
```
You translate reconstructed Korean meeting speech into formal, natural English.

INPUTS: same fields as translate_es.md.

RULES:
- Formal, natural English suitable for a hospital/academic setting.
- Preserve technical meaning. Do NOT simplify medical, academic, or engineering terms.
- Names, institutions, datasets, acronyms, drug names, model names: keep unchanged.
- Numbers: keep numerals.
- Code-switched English terms: keep verbatim (the speaker likely intended the English form).
- Output VALID JSON only.

OUTPUT JSON:
{
  "translated_text": "string",
  "confidence": "high" | "medium" | "low",
  "uncertainties": ["string", ...]
}
```

### `prompts/translate_zh.md`
```
You translate reconstructed Korean meeting speech into formal, natural Simplified Chinese (zh-CN).

INPUTS: same fields as translate_es.md.

RULES:
- Formal, natural Simplified Chinese suitable for a hospital/academic setting.
- Preserve technical meaning. Do NOT simplify medical, academic, or engineering terms.
- Names, institutions, datasets, acronyms, drug names, model names: keep unchanged unless a widely accepted Chinese equivalent exists. When in doubt, keep the original.
- Numbers: keep numerals (Arabic, not Chinese numerals).
- Code-switched English terms: keep in English.
- Output VALID JSON only.

OUTPUT JSON:
{
  "translated_text": "string",
  "confidence": "high" | "medium" | "low",
  "uncertainties": ["string", ...]
}
```

### `prompts/image_context.md`
```
You analyze an image uploaded as context for a Korean academic or technical meeting (likely medical, biomedical, or engineering).

EXTRACT:
1. visible_text: any text legible in the image, transcribed verbatim (preserve original language)
2. entities: people, institutions, products, datasets named or implied
3. technical_terms: domain-specific vocabulary visible
4. agenda_items: if the image is a slide or document, what topics it covers
5. likely_relevance: one or two sentences on how this image probably relates to a meeting

RULES:
- Do not infer beyond visible evidence.
- Do not invent hidden content.
- If the image is unclear or non-relevant, return empty arrays and a short note.
- Output VALID JSON only.

OUTPUT JSON:
{
  "visible_text": "string",
  "entities": ["string", ...],
  "technical_terms": ["string", ...],
  "agenda_items": ["string", ...],
  "likely_relevance": "string"
}
```

### `prompts/operational_summary.md`
```
You generate an operational meeting summary in Markdown from a Korean-source meeting transcribed and translated by an automated pipeline.

INPUTS:
- meeting_prompt: free-text context
- reconstructed_ko_full: full concatenated reconstructed Korean
- translated_full: full concatenated translation in the user's target language
- image_contexts: structured extractions from uploaded images
- segment_uncertainties: list of uncertainties flagged at segment level
- target_language: "es" | "en" | "zh"

OUTPUT: Markdown only. No JSON, no prose preamble. Target the chosen language for the body but keep section headings in English.

STRUCTURE (use these exact headings):

# Operational Summary

## 1. Executive Summary
2–4 sentences in the target language.

## 2. Key Decisions
Only explicit or strongly supported decisions. Bullets. If none, write "No explicit decisions recorded."

## 3. Action Items
Markdown table with columns: Task | Owner | Deadline | Evidence | Confidence
- "Owner" or "Deadline" unknown: write "Not specified".
- "Evidence": short Korean or original-language quote (≤ 12 words) or paraphrase.
- "Confidence": high/medium/low based on transcript confidence and clarity of commitment.

## 4. Open Questions
Bulleted list of unresolved points.

## 5. Technical Terms and Clarifications
Bulleted list. For each: term — short clarification.

## 6. Risks and Uncertainties
Combine transcript uncertainties with substantive risks discussed.

## 7. Chronological Summary
Concise timeline of the conversation. 5–12 bullets, in order.

RULES:
- Do not invent decisions, owners, deadlines, or commitments.
- Do not pad. Be operational and concise.
- If a section is genuinely empty, say so in one sentence.
- Output Markdown only.
```

### `prompts/judge_prompt_quality.md`
```
You are an evaluator scoring an LLM output against expected constraints for a Korean-meeting interpretation pipeline.

INPUTS:
- task_type: "reconstruct" | "translate" | "summary"
- input: the original input given to the candidate model
- output: the candidate model's response
- expected_constraints: rubric and constraints (not exact expected text)
- target_language: "es" | "en" | "zh" | null

SCORING (1–5):
- accuracy: does the output match the meaning expressed by the input?
- no_hallucination: 5 = no invented content; 1 = significant fabrication
- terminology_preservation: are names, datasets, technical terms preserved as required?
- uncertainty_handling: are uncertainties flagged when they should be?
- target_language_fluency: how natural is the target-language output? (set to 5 for reconstruct task)

CRITICAL FAILURES (any of these forces pass=false):
- inventing a fact, name, decision, deadline, or owner not present in input
- mistranslating a drug name or numeric value
- silently omitting an explicit decision or commitment
- producing invalid JSON when JSON was required

PASS CRITERIA:
- accuracy ≥ 4
- no_hallucination = 5
- terminology_preservation ≥ 4
- uncertainty_handling ≥ 4
- target_language_fluency ≥ 4
- no critical failures

Output VALID JSON only:
{
  "scores": {
    "accuracy": int,
    "no_hallucination": int,
    "terminology_preservation": int,
    "uncertainty_handling": int,
    "target_language_fluency": int
  },
  "critical_failures": ["string", ...],
  "pass": bool,
  "reason": "string",
  "suggested_prompt_changes": ["string", ...]
}
```

---

## 9. Tests

### 9.1 Markers (`pytest.ini` or `pyproject.toml`)
```
markers =
  unit: fast, no network
  integration: in-process, mocked external APIs
  e2e: full stack via test client or browser
  live_api: hits real OpenAI/Soniox (excluded by default)
  live_llm_judge: hits real LLM judges (excluded by default)
```

Default `pytest` runs `unit` and `integration` only. Live runs are explicit:
```
pytest -m live_api
pytest tests/prompt_eval --live-llm-judge
```

### 9.2 Unit tests
Cover everything in §6.3, §6.4 (factory routing), §6.5 (retroactive trigger heuristic), audio overlap drop, schema validation (target_language whitelist), markdown writer, cleanup, image context schema parsing, LLM JSON parsing (valid / malformed / missing fields), fallback behavior (one ASR fails, both empty, LLM returns invalid JSON → retry once then fail gracefully).

### 9.3 Integration tests
Use FastAPI's `TestClient`. Mock OpenAI and Soniox at the HTTP layer (e.g. with `respx` or `httpx_mock`). For each scenario:
- Start session → 200, returns id
- Post chunk with mocked ASR responses → both providers called concurrently (assert with timing or `asyncio.gather` mock); agreement scored; segment saved
- Post second chunk that introduces a new term → previous segment is retroactively revised; older one is finalized
- Image upload → vision endpoint called with base64; image_context stored
- Summary endpoint → summary LLM called; summary.md written
- GET summary.md → 200 with markdown content-type
- DELETE session → 204 / 200; folder removed

### 9.4 Frontend tests (Vitest + React Testing Library)
- LanguageSelector updates state and disables Start until selected
- ContextPromptBox updates state on input
- ImageUploader calls API on file select (mocked fetch)
- RecorderControls invokes recorder start/stop
- TranscriptView renders Korean and translation, badges, revision status
- SummaryButton appears only after stop

### 9.5 E2E (Playwright)
One spec covering the happy path:
1. Start session, choose Spanish, fill context, upload image
2. Inject 3 mocked audio chunks (use Playwright's request interception to fake ASR responses on the backend, OR run with a backend that uses the integration mocks)
3. Verify transcript renders 3 segments
4. Stop, generate summary, verify download attribute and content-type

### 9.6 Prompt evaluation gate
Seeds at `tests/prompt_eval/seeds/`:
- `01_academic_ko_es.json`: KO meeting about a research collaboration → ES
- `02_medical_ko_es.json`: KO discussion of a clinical case study (no patient identifiers) → ES
- `03_academic_ko_zh.json`: KO meeting → ZH
- `04_academic_ko_en.json`: KO meeting → EN
- `05_asr_disagreement_terminology.json`: OpenAI says "MIMIC-3", Soniox says "MIMIC-IV"; image context shows MIMIC-IV → expected: pick MIMIC-IV
- `06_low_confidence.json`: both ASRs disagree heavily, low lexical similarity → expected: confidence "low", uncertainties non-empty
- `07_summary_with_action_items.json`: transcript has 2 explicit action items, one without deadline → expected summary table preserves both, "Not specified" for missing deadline

Each seed JSON contains: `task_type`, `input` (matching what reconstruct/translate/summary would receive), `expected_constraints` (free-text rubric).

`run_eval.py` runs candidate prompts against seeds, calls both judges, applies pass criteria, writes `tests/prompt_eval/eval_results/{timestamp}/` with per-seed JSON and a summary.

`test_prompt_quality.py`:
- Default mode: judges are mocked (canned passing responses), the test verifies the gate logic itself (parsing, pass/fail, threshold application).
- `--live-llm-judge`: real judge calls. Skipped unless flag is passed.

If a prompt fails in live mode, optionally enter rewrite loop up to `MAX_PROMPT_REWRITE_ATTEMPTS`: feed judge's `suggested_prompt_changes` back as a meta-prompt to the reconstruction model, save each version under `eval_results/`. Stop after max attempts and surface clearly.

### 9.7 CI
GitHub Actions (`.github/workflows/ci.yml`):
- Job 1: backend unit + integration (mocked) — `pytest -m "unit or integration"`
- Job 2: frontend — `npm ci && npm run test && npm run build`
- Job 3: e2e — Playwright against the `docker compose up` stack with mocked external APIs
- Live API and live judge jobs: defined but `if: false` by default; user can flip to true manually.

---

## 10. Docker

`Dockerfile` (backend): python:3.12-slim base, install ffmpeg, copy backend, install deps via uv or pip, expose 8000, healthcheck `curl -f http://localhost:8000/api/health`.

`frontend/Dockerfile`: node:20-alpine, build static, serve via `serve` or nginx-alpine multi-stage. Expose 5173 in dev, 80 in prod.

`docker-compose.yml`:
- `backend` service: build `.`, env_file `.env`, volume `./data:/app/data`, ports `${BACKEND_PORT}:8000`, healthcheck
- `frontend` service: build `./frontend`, env `VITE_API_BASE=http://localhost:${BACKEND_PORT}`, depends_on backend healthy, ports `${FRONTEND_PORT}:5173` (dev) or `:80` (prod)

`Makefile`:
```
build:        docker compose build
up:           docker compose up -d
down:         docker compose down
logs:         docker compose logs -f
test:         pytest -m "unit or integration" && cd frontend && npm test
test-live:    pytest -m live_api
eval:         python -m tests.prompt_eval.run_eval
eval-live:    pytest tests/prompt_eval --live-llm-judge
clean:        docker compose down -v && rm -rf data/*
```

---

## 11. README

Sections (in order):
1. Project purpose (1 paragraph)
2. Architecture diagram (ASCII)
3. Quick start (clone → cp .env.example .env → fill keys → `make up`)
4. `.env` reference table
5. Docker deployment (VPS hint: nginx reverse proxy, HTTPS via Caddy or Let's Encrypt)
6. Local dev (without Docker)
7. Running tests (`make test`, `make test-live`)
8. Running prompt evaluation (`make eval`, `make eval-live`)
9. API endpoints (table form, brief)
10. **Data retention policy:** sessions auto-deleted after 24 hours, no patient data, no PII should be processed
11. **Disclaimer:** "This tool is an assistance aid and may contain transcription or translation errors. Do not rely on it as the sole record of medical, legal, or contractual statements."

---

## 12. Self-Correction Protocol

When something breaks:

1. **Test fails:** read the failure, locate the assertion, inspect the relevant code, fix the underlying issue (not the assertion). If the assertion is wrong, fix it AND verify against the spec in this document.
2. **Docker won't start:** read logs, identify the service. Common causes: port collision (`lsof -i :8000`), missing env var, image build error, healthcheck timeout. Resolve, rebuild, retry.
3. **Live API call fails 401/403:** check the relevant key in `.env`. If clearly invalid, stop and tell the user. Do not silently fall back to mocks for verification runs.
4. **Live API call fails 4xx other:** read the error body, check the request shape against the provider's current docs (you may need to web-search the latest endpoint signature).
5. **Live API call fails 5xx or timeout:** retry with exponential backoff up to 3 attempts; if still failing, log and continue to the next verification step but flag it in your final report.
6. **Frontend build fails:** read the error, fix imports/types/config; never disable strict mode to make errors go away.
7. **You find an internal contradiction in this spec:** stop, surface the contradiction to the user with the two conflicting clauses quoted, and propose a resolution. Do not proceed silently.

---

## 13. Final Acceptance Checklist

You are done when **every** item below is verified by you, in this order:

### Build & infra
- [ ] `git status` clean except for the new files; `.env` is gitignored
- [ ] `docker compose build` succeeds with no warnings about deprecated syntax
- [ ] `docker compose up -d` brings backend healthy within 30 s (`curl http://localhost:8000/api/health` returns `{"status":"ok"}`)
- [ ] Frontend reachable at `http://localhost:5173` and renders the initial screen

### Backend tests
- [ ] `pytest -m unit` — all green
- [ ] `pytest -m integration` — all green
- [ ] At least one live verification: a real call to OpenAI ASR with a 1-sentence Korean WAV, a real call to Soniox with the same, a real call to gpt-5.4-mini for reconstruction, a real call to gpt-5.4-nano with one image. All produce well-formed responses. Capture the responses in `tests/fixtures/asr_responses/` for future mocked tests.

### Frontend tests
- [ ] `npm run test` — all green
- [ ] `npm run build` — succeeds, dist/ produced

### E2E
- [ ] Playwright spec passes against `docker compose up` stack (with backend in mocked-external mode for ASR/LLM)

### Functional walk-through (you do this manually with `curl` and a browser)
- [ ] `POST /api/session/start` with target=`es` → returns session_id; folder created on disk
- [ ] `POST .../chunk` with a real 15 s Korean WAV → returns segment with non-empty `reconstructed_ko` and `translated_text`, agreement metrics computed, both `openai_asr_ko` and `soniox_asr_ko` populated, `soniox_speakers` non-empty if the audio has speech
- [ ] Post a second chunk introducing a new term → response includes a revised previous segment (`revision_status: "revised"`)
- [ ] `POST .../context/images` with a slide-like PNG → `extracted` contains plausible terms
- [ ] `POST .../summary` → returns download URL
- [ ] `GET .../summary.md` → returns Markdown with all 7 sections, in the correct target language for body, headings in English
- [ ] `DELETE` → folder removed
- [ ] Repeat the walk-through with target=`en` and target=`zh` (at minimum: start session + summary endpoint, can reuse same audio)

### Cleanup task
- [ ] Manually backdate a `manifest.json.created_at` to 25 hours ago, wait one cleanup cycle (or trigger manually) → folder removed

### Prompt eval
- [ ] `make eval` (mocked judges) — all 7 seeds pass the gate logic
- [ ] `make eval-live` documented in README, not run automatically

### Docs
- [ ] README has all 11 sections
- [ ] `.env.example` matches §5.1 exactly
- [ ] Architecture diagram present

### Hygiene
- [ ] No `print()` debug statements in committed code; use the `logging` module
- [ ] No commented-out code blocks
- [ ] Type hints on every public function in backend
- [ ] No `any` in new TypeScript except where genuinely unavoidable, with a comment

### State files
- [ ] `BUILD_PROMPT.md` committed at repo root, unmodified from what the user provided (this document)
- [ ] `BUILD_PROGRESS.md` committed at repo root, fully reflects 100 % completion: every Phase ticked, every §13 item ticked, `Next action` reads `none — build complete`, Verification log contains entries for every live API call and every Phase gate
- [ ] `BUILD_REPORT.md` committed at repo root (see §15)

---

## 14. Hard Constraints (DO NOT)

- DO NOT add authentication, user accounts, billing, quota, or cost tracking.
- DO NOT introduce WebSockets.
- DO NOT introduce a database. Filesystem only.
- DO NOT use Whisper, Clova, or any local model.
- DO NOT add languages beyond es/en/zh.
- DO NOT change the model assignments in §3.3 without telling the user first.
- DO NOT commit `.env`.
- DO NOT skip live verification before declaring done.
- DO NOT mark a task done while any test is red.
- DO NOT paraphrase the prompt files in §8 — they are verbatim.

---

## 15. Reporting Back

When you finish, produce `BUILD_REPORT.md` at the repo root. It is distinct from `BUILD_PROGRESS.md`: progress is the running log; report is the final summary. It must contain:
- Commit hash of the final state
- Output of all verification commands (truncated reasonably) — these can reference entries in `BUILD_PROGRESS.md` rather than duplicating them
- The captured live-API fixture filenames
- Any deviations from this spec, with justification (also surfaced in `BUILD_PROGRESS.md` Deviations section)
- Known issues or follow-ups

Make sure `BUILD_PROGRESS.md` is fully up to date and reflects 100 % complete state before you write `BUILD_REPORT.md`.

Then — and only then — tell the user "done" with a one-line summary plus a pointer to `BUILD_REPORT.md`.

Begin.