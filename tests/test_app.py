"""Smoke checks for import safety and the actual Streamlit render path."""

import importlib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def test_app_module_is_importable() -> None:
    module = importlib.import_module("app.main")

    assert callable(module.main)


def test_homepage_renders_without_api_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # Use known non-secret settings even if a developer has a local .env file.
    monkeypatch.setenv("AURA_APP_NAME", "Aura 2.0 — Agentic AI Career Assistant")
    monkeypatch.setenv("AURA_APP_ENV", "test")
    app_file = Path(__file__).resolve().parents[1] / "app" / "main.py"

    page = AppTest.from_file(str(app_file)).run()

    assert not page.exception
    assert page.title[0].value == "Aura 2.0 — Agentic AI Career Assistant"
    assert page.markdown[0].value == "Your personal AI companion for smarter job searching."
    assert [heading.value for heading in page.subheader] == [
        "Your career workspace",
        "CV Intelligence",
        "Job Matching",
        "Application Studio",
        "Application Tracking",
        "Interview Preparation",
    ]
    assert sum("Coming Soon" in caption.value for caption in page.caption) == 5
