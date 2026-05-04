from __future__ import annotations

import os
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI (ASR models are separate from chat models)
    openai_api_key: str = ""
    openai_asr_model: str = "gpt-4o-transcribe"

    # Soniox
    soniox_api_key: str = ""
    soniox_model: str = "stt-async-v4"

    # LLM stack (GPT-5.4 series)
    llm_provider_reconstruct: str = "openai"
    llm_model_reconstruct: str = "gpt-5.4-mini"

    llm_provider_translate: str = "openai"
    llm_model_translate: str = "gpt-5.4-mini"

    llm_provider_vision: str = "openai"
    llm_model_vision: str = "gpt-5.4-nano"

    llm_provider_summary: str = "openai"
    llm_model_summary: str = "gpt-5.4"

    llm_provider_judge_a: str = "openai"
    llm_model_judge_a: str = "gpt-5.4"

    llm_provider_judge_b: str = "openai"
    llm_model_judge_b: str = "gpt-5.4-nano"

    # Optional alternate provider keys
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Pipeline
    default_chunk_seconds: int = 15
    default_overlap_seconds: int = 2
    retroactive_correction_segments: int = 2
    context_window_segments: int = 6
    session_ttl_hours: int = 24
    data_dir: str = "/app/data"
    max_image_mb: int = 10

    # Eval
    max_prompt_rewrite_attempts: int = 3

    # Auth
    auth_enabled: bool = False
    admin_password: str = ""  # Set this to enable login
    auth_pepper: str = "change-this-in-production"

    # Server
    backend_port: int = 8000
    frontend_port: int = 5173
    cors_origins: str = "http://localhost:5173"

    @field_validator("data_dir", mode="before")
    @classmethod
    def resolve_data_dir(cls, v: str) -> str:
        return os.path.expandvars(os.path.expanduser(v))

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_mb * 1024 * 1024


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
