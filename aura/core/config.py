"""Validated settings loaded from the environment and the project-root .env file."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDF_MAX_SIZE_MB = 10


class Settings(BaseSettings):
    """Application settings; local PDF extraction works without Gemini credentials."""

    model_config = SettingsConfigDict(
        env_prefix="AURA_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = Field(default="Aura 2.0 — Agentic AI Career Assistant", min_length=1)
    app_env: Literal["development", "test", "production"] = "development"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    agent_model: str = Field(default="gemini-3.5-flash-lite", min_length=1)
    agent_max_model_calls: int = Field(default=6, ge=2, le=12)
    agent_max_turns: int = Field(default=10, ge=1, le=20)
    pdf_max_size_mb: int = Field(
        default=DEFAULT_PDF_MAX_SIZE_MB, ge=1, description="Maximum PDF upload size in MiB."
    )
