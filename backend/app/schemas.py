from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


TargetLanguage = Literal["es", "en", "zh"]
RevisionStatus = Literal["draft", "revised", "final"]
ConfidenceLevel = Literal["high", "medium", "low"]


class SessionStartRequest(BaseModel):
    target_language: TargetLanguage
    meeting_prompt: str = ""
    chunk_seconds: int = 15
    overlap_seconds: int = 2

    @field_validator("chunk_seconds")
    @classmethod
    def chunk_seconds_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("chunk_seconds must be positive")
        return v

    @field_validator("overlap_seconds")
    @classmethod
    def overlap_seconds_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("overlap_seconds must be non-negative")
        return v


class SessionStartResponse(BaseModel):
    session_id: str


class SpeakerSegment(BaseModel):
    speaker: str
    text: str


class AgreementMetrics(BaseModel):
    lexical_similarity: float
    length_ratio: float
    confidence_hint: ConfidenceLevel


class RevisionHistoryEntry(BaseModel):
    timestamp: str
    reason: str
    previous_reconstructed_ko: str


class Segment(BaseModel):
    segment_id: str
    chunk_index: int
    time_start: float
    time_end: float
    openai_asr_ko: str = ""
    soniox_asr_ko: str = ""
    soniox_speakers: list[SpeakerSegment] = Field(default_factory=list)
    openai_asr_error: str | None = None
    soniox_asr_error: str | None = None
    reconstructed_ko: str = ""
    translated_text: str = ""
    target_language: TargetLanguage = "es"
    confidence: ConfidenceLevel = "low"
    uncertainties: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)
    agreement: AgreementMetrics | None = None
    revision_status: RevisionStatus = "draft"
    revision_history: list[RevisionHistoryEntry] = Field(default_factory=list)
    asr_sources: list[str] = Field(default_factory=list)  # e.g., ["openai"], ["soniox"], or ["openai", "soniox"]


class ChunkResponse(BaseModel):
    chunk_index: int
    status: str
    segments: list[Segment]


class ImageContext(BaseModel):
    image_id: str
    filename: str
    visible_text: str = ""
    entities: list[str] = Field(default_factory=list)
    technical_terms: list[str] = Field(default_factory=list)
    agenda_items: list[str] = Field(default_factory=list)
    likely_relevance: str = ""


class ImageUploadResponse(BaseModel):
    image_ids: list[str]
    extracted: list[ImageContext]


class TranscriptResponse(BaseModel):
    session_id: str
    target_language: TargetLanguage
    meeting_prompt: str
    image_contexts: list[ImageContext]
    segments: list[Segment]


class SummaryResponse(BaseModel):
    status: str
    download_url: str


class SessionManifest(BaseModel):
    session_id: str
    target_language: TargetLanguage
    meeting_prompt: str
    chunk_seconds: int
    overlap_seconds: int
    created_at: str
    segments: list[Segment] = Field(default_factory=list)
    image_contexts: list[ImageContext] = Field(default_factory=list)
    summary_generated: bool = False
    summary_filename: str | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
