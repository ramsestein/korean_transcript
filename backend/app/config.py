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

    # LLM stack
    llm_provider_reconstruct: str = "google"
    llm_model_reconstruct: str = "gemini-2.5-flash"

    llm_provider_translate: str = "google"
    llm_model_translate: str = "gemini-2.5-flash"

    llm_provider_vision: str = "openai"
    llm_model_vision: str = "gpt-5.4-nano"

    llm_provider_summary: str = "openai"
    llm_model_summary: str = "gpt-5.4-mini"

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
    logs_dir: str = "/app/logs"
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

    @field_validator("data_dir", "logs_dir", mode="before")
    @classmethod
    def resolve_data_dir(cls, v: str) -> str:
        return os.path.expandvars(os.path.expanduser(v))

    @field_validator("google_api_key", mode="before")
    @classmethod
    def resolve_google_key(cls, v: str) -> str:
        # Allow using GEMINI_API_KEY in env/.env as an alias for google_api_key
        if v:
            return v
        return os.environ.get('GEMINI_API_KEY', '')

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
        # Ensure GEMINI_API_KEY from .env is available as GOOGLE_API_KEY
        try:
            if not os.environ.get('GOOGLE_API_KEY'):
                # prefer environment first
                if os.environ.get('GEMINI_API_KEY'):
                    os.environ['GOOGLE_API_KEY'] = os.environ['GEMINI_API_KEY']
                else:
                    for cand in (Path('.env'), Path('../.env')):
                        try:
                            if cand.exists():
                                with cand.open('r', encoding='utf-8') as f:
                                    for line in f:
                                        line = line.strip()
                                        if not line or line.startswith('#') or '=' not in line:
                                            continue
                                        k, v = line.split('=', 1)
                                        k = k.strip()
                                        v = v.strip().strip('"').strip("'")
                                        if k == 'GEMINI_API_KEY' and v:
                                            os.environ['GOOGLE_API_KEY'] = v
                                            break
                                if os.environ.get('GOOGLE_API_KEY'):
                                    break
                        except Exception:
                            continue
        except Exception:
            pass
        _settings = Settings()
    return _settings
