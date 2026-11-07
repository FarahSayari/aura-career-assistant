"""Settings tests use temporary dotenv files and never read personal credentials."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from aura.core.config import Settings


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep developer-specific Aura environment variables out of every test."""
    for name in os.environ:
        if name.upper().startswith("AURA_"):
            monkeypatch.delenv(name)


def test_defaults_work_without_dotenv_or_api_key() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "Aura 2.0 — Agentic AI Career Assistant"
    assert settings.app_env == "development"
    assert settings.gemini_api_key is None


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AURA_APP_NAME", "Aura Preview")
    monkeypatch.setenv("AURA_APP_ENV", "test")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Aura Preview"
    assert settings.app_env == "test"


def test_dotenv_loads_utf8_and_ignores_unrelated_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'AURA_APP_NAME="Aura carrière"\nAURA_APP_ENV=test\nUNRELATED_SETTING=value\n',
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "Aura carrière"
    assert settings.app_env == "test"


def test_environment_takes_precedence_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("AURA_APP_ENV=production\n", encoding="utf-8")
    monkeypatch.setenv("AURA_APP_ENV", "test")

    assert Settings(_env_file=env_file).app_env == "test"


def test_explicit_settings_take_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AURA_APP_ENV", "production")

    assert Settings(app_env="test", _env_file=None).app_env == "test"


@pytest.mark.parametrize("app_env", ["development", "test", "production"])
def test_supported_environments(app_env: str) -> None:
    assert Settings(app_env=app_env, _env_file=None).app_env == app_env


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AURA_APP_ENV", "unknown")

    with pytest.raises(ValidationError, match="app_env"):
        Settings(_env_file=None)


def test_empty_app_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="app_name"):
        Settings(app_name="", _env_file=None)


def test_blank_optional_key_uses_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("AURA_GEMINI_API_KEY=\n", encoding="utf-8")
    monkeypatch.setenv("AURA_GEMINI_API_KEY", "")

    assert Settings(_env_file=env_file).gemini_api_key is None


def test_api_key_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_key = "synthetic-test-key-never-a-real-credential"
    monkeypatch.setenv("AURA_GEMINI_API_KEY", fake_key)

    settings = Settings(_env_file=None)

    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == fake_key
    assert fake_key not in repr(settings)
    assert fake_key not in settings.model_dump_json()
