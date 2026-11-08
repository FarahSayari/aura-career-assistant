"""Validated settings loaded from the environment and the project-root .env file."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """M0 settings; Gemini credentials remain optional until an AI feature needs them."""

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
