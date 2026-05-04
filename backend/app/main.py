from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.asr.agreement import compute_agreement
from app.asr.parallel_asr import run_parallel_asr
from app.audio.chunking import build_augmented_clip
from app.audio.convert import convert_to_wav_16k_mono
from app.audio.overlap import drop_prefix_tokens, tokens_to_speaker_turns, tokens_to_text
from app.config import Settings, get_settings
from app.deps import verify_session
from app.llm.image_context import extract_image_context
from app.llm.reconstruct import reconstruct_korean
from app.llm.translate import translate_korean
from app.output.summary_export import export_summary
from app.schemas import (
    AgreementMetrics,
    ChunkResponse,
    ImageContext,
    ImageUploadResponse,
    Segment,
    SessionManifest,
    SessionStartRequest,
    SessionStartResponse,
    SpeakerSegment,
    SummaryResponse,
    TranscriptResponse,
)
from app.session.cleanup import run_cleanup_loop
from app.session.manager import (
    add_image_context,
    append_segment,
    create_session,
    delete_session,
    get_session_manifest,
    save_session_manifest,
    update_segment,
)
from app.session.store import session_dir, write_json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ko-meeting-interpreter", version="0.1.0")


@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    asyncio.create_task(run_cleanup_loop(settings))
    logger.info("ko-meeting-interpreter backend started, data_dir=%s", settings.data_dir)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/auth/status")
async def auth_status(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    """Check if authentication is enabled."""
    from app.auth import list_usernames
    return {
        "auth_enabled": settings.auth_enabled,
        "users_configured": list_usernames() if settings.auth_enabled else []
    }


@app.post("/api/auth/login")
async def login(request: Request) -> JSONResponse:
    """Login with username/password and receive a token."""
    from app.auth import authenticate_user, get_token_username
    
    settings = get_settings()
    
    # If auth is disabled, return a dummy token
    if not settings.auth_enabled:
        return JSONResponse({"token": "disabled", "username": "anonymous", "message": "Authentication is disabled"})
    
    # Parse JSON body with better error handling
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse login request body: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {str(e)}")
    
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    
    username = body.get("username", "").strip() if body.get("username") else ""
    password = body.get("password", "") if body.get("password") else ""
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    
    token, error_message = authenticate_user(username, password, client_ip)
    if not token:
        raise HTTPException(status_code=401, detail=error_message)
    
    actual_username = get_token_username(token) or username
    return JSONResponse({"token": token, "username": actual_username, "message": "Login successful"})


@app.post("/api/auth/logout")
async def logout(request: Request) -> JSONResponse:
    """Logout and invalidate the token."""
    from app.auth import revoke_token
    
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        revoke_token(token)
    
    return JSONResponse({"message": "Logout successful"})


@app.post("/api/session/start", response_model=SessionStartResponse)
async def session_start(
    request: SessionStartRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Depends(require_auth)],
) -> SessionStartResponse:
    logger.info("Session start called with lang=%s, token=%s...", request.target_language, token[:10] if token else 'none')
    session_id = await create_session(request, settings)
    logger.info("Created session %s (lang=%s)", session_id, request.target_language)
    return SessionStartResponse(session_id=session_id)


@app.post("/api/session/{session_id}/chunk", response_model=ChunkResponse)
async def upload_chunk(
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Depends(require_auth)],
    audio: UploadFile = File(...),
    chunk_index: int = Form(...),
    local_start_time: float = Form(...),
    local_end_time: float = Form(...),
) -> ChunkResponse:
    manifest = await get_session_manifest(session_id, settings)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    base = session_dir(settings.data_dir, session_id)
    ext = Path(audio.filename or "chunk.webm").suffix or ".webm"
    raw_path = base / "audio_raw" / f"{chunk_index}{ext}"
    wav_path = base / "audio_processed" / f"{chunk_index}.wav"
    aug_path = base / "audio_processed" / f"{chunk_index}_aug.wav"

    audio_bytes = await audio.read()
    async with aiofiles.open(raw_path, "wb") as f:
        await f.write(audio_bytes)

    try:
        await convert_to_wav_16k_mono(raw_path, wav_path)
    except Exception as exc:
        import traceback as _tb
        detail = f"Audio conversion failed [{type(exc).__name__}]: {exc!r}"
        logger.error("Audio conversion for chunk %d: %s\n%s", chunk_index, detail, _tb.format_exc())
        raise HTTPException(status_code=422, detail=detail) from exc

    prev_wav = base / "audio_processed" / f"{chunk_index - 1}.wav" if chunk_index > 0 else None
    actual_overlap = await build_augmented_clip(
        current_wav=wav_path,
        previous_wav=prev_wav,
        overlap_seconds=manifest.overlap_seconds,
        output_path=aug_path,
    )

    openai_result, soniox_result, openai_error, soniox_error = await run_parallel_asr(
        audio_path=aug_path,
        openai_api_key=settings.openai_api_key,
        soniox_api_key=settings.soniox_api_key,
        openai_model=settings.openai_asr_model,
        soniox_model=settings.soniox_model,
    )

    if openai_result is None and soniox_result is None:
        raise HTTPException(status_code=502, detail="Both ASR providers failed")

    openai_tokens = (openai_result or {}).get("tokens", [])
    soniox_tokens = (soniox_result or {}).get("tokens", [])

    if actual_overlap > 0:
        openai_tokens = drop_prefix_tokens(openai_tokens, actual_overlap)
        soniox_tokens = drop_prefix_tokens(soniox_tokens, actual_overlap)

    openai_text = tokens_to_text(openai_tokens) if openai_tokens else (openai_result or {}).get("text", "")
    soniox_text = tokens_to_text(soniox_tokens) if soniox_tokens else (soniox_result or {}).get("text", "")

    if not openai_text and openai_result:
        openai_text = openai_result.get("text", "")
    if not soniox_text and soniox_result:
        soniox_text = soniox_result.get("text", "")

    speaker_turns_raw = tokens_to_speaker_turns(soniox_tokens)
    soniox_speakers = [SpeakerSegment(speaker=t["speaker"], text=t["text"]) for t in speaker_turns_raw]

    agreement_raw = compute_agreement(openai_text, soniox_text)
    agreement = AgreementMetrics(
        lexical_similarity=agreement_raw["lexical_similarity"],
        length_ratio=agreement_raw["length_ratio"],
        confidence_hint=agreement_raw["confidence_hint"],
    )

    await write_json(
        base / "asr" / f"chunk_{chunk_index}.json",
        {
            "openai": openai_result,
            "soniox": soniox_result,
            "openai_error": openai_error,
            "soniox_error": soniox_error,
            "openai_text_clean": openai_text,
            "soniox_text_clean": soniox_text,
            "agreement": agreement_raw,
        },
    )

    recon_result = await reconstruct_korean(
        openai_asr_ko=openai_text,
        soniox_asr_ko=soniox_text,
        soniox_speakers=[t.model_dump() for t in soniox_speakers],
        agreement=agreement,
        previous_segments=manifest.segments,
        meeting_prompt=manifest.meeting_prompt,
        image_contexts=manifest.image_contexts,
        settings=settings,
    )

    trans_result = await translate_korean(
        reconstructed_ko=recon_result["reconstructed_ko"],
        target_language=manifest.target_language,
        previous_segments=manifest.segments,
        meeting_prompt=manifest.meeting_prompt,
        image_contexts=manifest.image_contexts,
        settings=settings,
    )

    segment_id = f"{session_id}_{chunk_index}"
    new_segment = Segment(
        segment_id=segment_id,
        chunk_index=chunk_index,
        time_start=local_start_time,
        time_end=local_end_time,
        openai_asr_ko=openai_text,
        soniox_asr_ko=soniox_text,
        soniox_speakers=soniox_speakers,
        openai_asr_error=openai_error,
        soniox_asr_error=soniox_error,
        reconstructed_ko=recon_result["reconstructed_ko"],
        translated_text=trans_result["translated_text"],
        target_language=manifest.target_language,
        confidence=recon_result["confidence"],
        uncertainties=recon_result["uncertainties"],
        terminology=recon_result["terminology"],
        agreement=agreement,
        revision_status="draft",
    )

    await append_segment(session_id, new_segment, settings)

    await write_json(
        base / "llm" / f"segment_{chunk_index}.json",
        new_segment.model_dump(),
    )

    touched_segments = [new_segment]

    manifest = await get_session_manifest(session_id, settings)
    if manifest is not None:
        revised = await _retroactive_correction(
            manifest=manifest,
            new_segment=new_segment,
            settings=settings,
        )
        touched_segments.extend(revised)

        manifest = await get_session_manifest(session_id, settings)
        if manifest:
            for seg in manifest.segments:
                if seg.revision_status == "draft":
                    cutoff = chunk_index - settings.retroactive_correction_segments
                    if seg.chunk_index < cutoff:
                        seg.revision_status = "final"
            await save_session_manifest(manifest, settings)

    return ChunkResponse(
        chunk_index=chunk_index,
        status="processed",
        segments=touched_segments,
    )


async def _retroactive_correction(
    manifest: SessionManifest,
    new_segment: Segment,
    settings: Settings,
) -> list[Segment]:
    """
    Re-run reconstruction+translation for previous RETROACTIVE_CORRECTION_SEGMENTS
    segments if new_segment introduces new terminology not seen before.
    """
    from app.session.context_window import collect_known_terminology

    new_terms = set(new_segment.terminology)
    existing_segments = [s for s in manifest.segments if s.segment_id != new_segment.segment_id]
    known_terms = collect_known_terminology(existing_segments, manifest.image_contexts)

    genuinely_new = new_terms - known_terms
    if not genuinely_new:
        return []

    logger.info(
        "Retroactive correction triggered by new terms: %s",
        genuinely_new,
    )

    n = settings.retroactive_correction_segments
    candidates = [
        s for s in manifest.segments
        if s.revision_status != "final" and s.segment_id != new_segment.segment_id
    ]
    candidates_sorted = sorted(candidates, key=lambda s: s.chunk_index, reverse=True)
    to_revise = candidates_sorted[:n]

    revised: list[Segment] = []
    for seg in to_revise:
        try:
            ctx_segs = [s for s in manifest.segments if s.chunk_index < seg.chunk_index]
            old_ko = seg.reconstructed_ko

            recon = await reconstruct_korean(
                openai_asr_ko=seg.openai_asr_ko,
                soniox_asr_ko=seg.soniox_asr_ko,
                soniox_speakers=[sp.model_dump() for sp in seg.soniox_speakers],
                agreement=seg.agreement or AgreementMetrics(
                    lexical_similarity=0.0, length_ratio=0.0, confidence_hint="low"
                ),
                previous_segments=ctx_segs,
                meeting_prompt=manifest.meeting_prompt,
                image_contexts=manifest.image_contexts,
                settings=settings,
            )

            diff_ratio = (
                abs(len(recon["reconstructed_ko"]) - len(old_ko)) / max(len(old_ko), 1)
            )

            if diff_ratio > 0.05:
                trans = await translate_korean(
                    reconstructed_ko=recon["reconstructed_ko"],
                    target_language=manifest.target_language,
                    previous_segments=ctx_segs,
                    meeting_prompt=manifest.meeting_prompt,
                    image_contexts=manifest.image_contexts,
                    settings=settings,
                )
                reason = f"New terms introduced: {', '.join(sorted(genuinely_new))}"
                seg.revision_history.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reason": reason,
                        "previous_reconstructed_ko": old_ko,
                    }
                )
                seg.reconstructed_ko = recon["reconstructed_ko"]
                seg.translated_text = trans["translated_text"]
                seg.terminology = recon["terminology"]
                seg.revision_status = "revised"
                await update_segment(manifest.session_id, seg, settings)
                revised.append(seg)
        except Exception as exc:
            logger.warning("Retroactive correction failed for segment %s: %s", seg.segment_id, exc)

    return revised


@app.post("/api/session/{session_id}/context/images", response_model=ImageUploadResponse)
async def upload_images(
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Depends(require_auth)],
    images: list[UploadFile] = File(...),
) -> ImageUploadResponse:
    manifest = await get_session_manifest(session_id, settings)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    base = session_dir(settings.data_dir, session_id)
    result_ids: list[str] = []
    extracted_contexts: list[ImageContext] = []

    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

    for upload in images:
        if upload.content_type and upload.content_type not in allowed_types:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported image type: {upload.content_type}",
            )
        img_bytes = await upload.read()
        if len(img_bytes) > settings.max_image_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Image '{upload.filename}' exceeds {settings.max_image_mb} MB limit",
            )

        img_id = str(uuid.uuid4())
        img_path = base / "images" / f"{img_id}{Path(upload.filename or 'img.jpg').suffix}"
        async with aiofiles.open(img_path, "wb") as f:
            await f.write(img_bytes)

        try:
            ctx_data = await extract_image_context(img_bytes, upload.filename or img_id, settings)
        except Exception as exc:
            logger.error("Image context extraction failed for %s: %s", upload.filename, exc)
            ctx_data = {
                "visible_text": "",
                "entities": [],
                "technical_terms": [],
                "agenda_items": [],
                "likely_relevance": f"Extraction failed: {exc}",
            }

        img_context = ImageContext(
            image_id=img_id,
            filename=upload.filename or img_id,
            **ctx_data,
        )

        await write_json(base / "images" / f"{img_id}.json", img_context.model_dump())
        await add_image_context(session_id, img_context, settings)

        result_ids.append(img_id)
        extracted_contexts.append(img_context)

    return ImageUploadResponse(image_ids=result_ids, extracted=extracted_contexts)


@app.get("/api/session/{session_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Depends(require_auth)],
) -> TranscriptResponse:
    manifest = await get_session_manifest(session_id, settings)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return TranscriptResponse(
        session_id=manifest.session_id,
        target_language=manifest.target_language,
        meeting_prompt=manifest.meeting_prompt,
        image_contexts=manifest.image_contexts,
        segments=sorted(manifest.segments, key=lambda s: s.chunk_index),
    )


@app.post("/api/session/{session_id}/summary", response_model=SummaryResponse)
async def generate_summary_endpoint(
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Depends(require_auth)],
) -> SummaryResponse:
    manifest = await get_session_manifest(session_id, settings)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        await export_summary(manifest, settings)
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {exc}") from exc

    manifest.summary_generated = True
    await save_session_manifest(manifest, settings)

    return SummaryResponse(
        status="generated",
        download_url=f"/api/session/{session_id}/summary.md",
    )


@app.get("/api/session/{session_id}/summary.md")
async def download_summary(
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Depends(require_auth)],
) -> FileResponse:
    summary_path = session_dir(settings.data_dir, session_id) / "summary.md"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Summary not yet generated")

    return FileResponse(
        path=str(summary_path),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="summary.md"'},
    )


@app.delete("/api/session/{session_id}")
async def end_session(
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str, Depends(require_auth)],
) -> dict:
    deleted = await delete_session(session_id, settings)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    logger.info("Deleted session %s", session_id)
    return {"status": "deleted", "session_id": session_id}
