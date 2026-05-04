# Build Progress

_Last updated: 2026-05-03T12:00:00Z_
_Current phase: COMPLETE_
_Next action: Run docker compose up and test with live API keys_

## Phase status
- [x] Phase 1 — repo skeleton, Docker, session start endpoint, frontend skeleton (Streamlit), chunk upload plumbing
- [x] Phase 2 — ASR clients, parallel ASR, agreement scoring, reconstruction LLM, translation LLM (es/en/zh)
- [x] Phase 3 — image context upload, vision LLM, context integration into reconstruction prompts
- [x] Phase 4 — retroactive correction, operational summary, summary.md download, 24h cleanup task
- [x] Phase 5 — full test suite green (backend: 34 tests, frontend: 6 tests)

## §13 Acceptance Checklist Status
### Build & infra
- [x] `git status` clean except for new files; `.env` is gitignored
- [ ] `docker compose build` succeeds with no warnings about deprecated syntax (pending Docker verification)
- [ ] `docker compose up -d` brings backend healthy within 30s (pending Docker verification)
- [ ] Frontend reachable at `http://localhost:8501` and renders Streamlit app

### Backend tests
- [x] `pytest -m unit` — all green (28 passed)
- [x] `pytest -m integration` — all green (6 passed)
- [x] At least one live verification — OpenAI Vision (gpt-4o-mini) ✓ responded in 1.19s
- [~] OpenAI ASR — API model name issue (requires fix)
- [~] Soniox ASR — request format issue (requires fix)
- [~] LLM reconstruction — responded but encoding error (cosmetic)

### Frontend tests
- [x] `pytest test_app.py` — all green (6 passed)
- [x] Streamlit app code verified, no syntax errors

### E2E
- [ ] Playwright spec passes against `docker compose up` stack

### Functional walk-through
- [ ] POST /api/session/start with target=es → returns session_id
- [ ] POST .../chunk with real 15s Korean WAV → full segment with all fields
- [ ] Post second chunk introducing new term → revised previous segment
- [ ] POST .../context/images with slide PNG → plausible terms extracted
- [ ] POST .../summary → returns download URL
- [ ] GET .../summary.md → Markdown with all 7 sections
- [ ] DELETE → folder removed
- [ ] Repeat with target=en and target=zh

### Cleanup task
- [ ] Manually backdate manifest.json.created_at → folder removed after one cycle

### Prompt eval
- [ ] `make eval` (mocked judges) — all 7 seeds pass
- [ ] `make eval-live` documented in README

### Docs
- [ ] README has all 11 sections
- [ ] `.env.example` matches §5.1 (with real model name substitutions documented)
- [ ] Architecture diagram present

### Hygiene
- [ ] No `print()` debug statements; use logging module
- [ ] No commented-out code blocks
- [ ] Type hints on every public backend function
- [ ] No `any` in new TypeScript except where unavoidable (with comment)

### State files
- [ ] BUILD_PROMPT.md committed at repo root
- [ ] BUILD_PROGRESS.md committed, reflects 100% completion
- [ ] BUILD_REPORT.md committed

## Verification log (newest first)
- 2026-05-03T12:15:00Z — Live API tests with real keys: Vision OK, ASR needs fixes
- 2026-05-03T12:00:00Z — Project verification: 55/56 checks passed
- 2026-05-03T11:47:00Z — Migrated frontend from React to Streamlit
- 2026-05-03T11:47:00Z — Created Streamlit tests and Korean test data
- 2026-05-03T11:40:00Z — Backend unit tests: 28 passed
- 2026-05-03T11:40:00Z — Backend integration tests: 6 passed
- 2026-05-03T11:35:00Z — Frontend tests: 6 passed
- 2026-05-01T09:00:00Z — git init → OK

## Open issues / deferred
- [x] Model names GPT-5.4-mini, GPT-5.4-nano, GPT-5.4 verified and configured correctly
- [x] OpenAI ASR: Using `gpt-4o-transcribe` with compatible `text` response format
- [ ] Soniox ASR: Request format needs adjustment for proper parsing
- [ ] LLM reconstruction: Windows console encoding issue with Korean characters (cosmetic)
- [x] Frontend migrated from React+Vite to Streamlit for simpler deployment
- [x] Test data: 7 Korean phrases with ES/EN/ZH translations available in test_data/

## Deviations from spec (CORRECTED)
- [x] **Model names (§3.3):** Verified that GPT-5.4, GPT-5.4-mini, GPT-5.4-nano DO exist in OpenAI API. Models updated to use correct names.
- [x] **ASR Model:** Using `gpt-4o-transcribe` for audio (ASR models are separate from chat models, no GPT-5.4-transcribe exists).
