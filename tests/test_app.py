"""Smoke checks for import safety and the actual Streamlit render path."""

import importlib
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from aura.schemas.cv_extraction import CvExtraction
from aura.services import gemini_extraction
from aura.services.profile_conversion import to_professional_profile


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
    assert sum("Coming Soon" in caption.value for caption in page.caption) == 4
    assert any("PDF text extraction available" in caption.value for caption in page.caption)


@pytest.fixture
def cv_page(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("AURA_APP_ENV", "test")
    monkeypatch.setenv("AURA_PDF_MAX_SIZE_MB", "1")
    monkeypatch.setenv("AURA_GEMINI_API_KEY", "synthetic-ui-api-key")
    monkeypatch.setenv("AURA_GEMINI_MODEL", "gemini-2.5-flash")
    app_file = Path(__file__).resolve().parents[1] / "app" / "main.py"
    page = AppTest.from_file(str(app_file)).run()
    return page.switch_page("pages/cv_intelligence.py").run()


def test_cv_page_waits_for_upload_and_explicit_extraction(
    cv_page: AppTest, make_pdf: Callable[[list[str]], bytes]
) -> None:
    assert not cv_page.exception
    assert cv_page.title[0].value == "CV Intelligence"
    assert cv_page.button[0].disabled

    cv_page.file_uploader[0].upload(
        "synthetic.pdf", make_pdf(["Synthetic CV text"]), "application/pdf"
    )
    cv_page.run()

    assert not cv_page.button[0].disabled
    assert not cv_page.text_area
    cv_page.button[0].click().run()

    assert not cv_page.exception
    assert cv_page.text_area[0].value == "Synthetic CV text"
    assert cv_page.metric[0].value == "1"
    assert len(cv_page.success) == 1


def test_cv_page_displays_each_page_and_metadata(
    cv_page: AppTest, make_pdf: Callable[[list[str]], bytes]
) -> None:
    cv_page.file_uploader[0].upload(
        "synthetic.pdf", make_pdf(["First page", "Second page"]), "application/pdf"
    )
    cv_page.run().button[0].click().run()

    assert not cv_page.exception
    assert cv_page.metric[0].value == "2"
    assert [area.value for area in cv_page.text_area] == ["First page", "Second page"]
    assert "Synthetic CV" in cv_page.json[0].value


def test_cv_page_shows_reading_order_fallback_warning(cv_page: AppTest) -> None:
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 80), "Isolated left label")
        page.insert_text((350, 180), "Isolated right label")
        pdf = document.tobytes()
    cv_page.file_uploader[0].upload("synthetic-layout.pdf", pdf, "application/pdf")
    cv_page.run().button[0].click().run()

    assert not cv_page.exception
    assert any(
        "original position-sorted extraction" in warning.value for warning in cv_page.warning
    )
    assert "Isolated left label" in cv_page.text_area[0].value
    assert "Isolated right label" in cv_page.text_area[0].value


@pytest.mark.parametrize("content", [b"not a PDF", b"%PDF-1.7\ncorrupted\n%%EOF", b""])
def test_cv_page_shows_safe_extraction_errors(cv_page: AppTest, content: bytes) -> None:
    cv_page.file_uploader[0].upload("synthetic.pdf", content, "application/pdf")
    cv_page.run().button[0].click().run()

    assert not cv_page.exception
    assert len(cv_page.error) == 1
    assert not cv_page.text_area
    assert not cv_page.success


def test_changing_or_removing_upload_clears_old_preview(
    cv_page: AppTest, make_pdf: Callable[[list[str]], bytes]
) -> None:
    cv_page.file_uploader[0].upload(
        "first.pdf", make_pdf(["First synthetic CV"]), "application/pdf"
    )
    cv_page.run().button[0].click().run()
    assert cv_page.text_area[0].value == "First synthetic CV"

    cv_page.file_uploader[0].upload(
        "second.pdf", make_pdf(["Second synthetic CV"]), "application/pdf"
    )
    cv_page.run()
    assert not cv_page.text_area
    cv_page.button[0].click().run()
    assert cv_page.text_area[0].value == "Second synthetic CV"

    cv_page.file_uploader[0].clear().run()
    assert not cv_page.text_area
    assert cv_page.button[0].disabled


@pytest.fixture
def extracted_cv_page(cv_page: AppTest, make_pdf: Callable[[list[str]], bytes]) -> AppTest:
    cv_page.file_uploader[0].upload("synthetic.pdf", make_pdf(["Alex Example"]), "application/pdf")
    return cv_page.run().button[0].click().run()


@pytest.fixture
def analysis_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    profile = to_professional_profile(
        CvExtraction(identity={"full_name": "Alex Example"}),
        document_name="synthetic.pdf",
        page_count=1,
    )
    mock = MagicMock(return_value=profile)
    monkeypatch.setattr(gemini_extraction, "extract_cv_profile", mock)
    return mock


def test_gemini_requires_both_confirmation_and_button_click(
    extracted_cv_page: AppTest, analysis_mock: MagicMock
) -> None:
    page = extracted_cv_page
    assert page.button(key="cv_analyze").disabled
    analysis_mock.assert_not_called()
    page.checkbox(key="cv_gemini_consent").check().run()
    analysis_mock.assert_not_called()
    assert not page.button(key="cv_analyze").disabled
    assert any("Google" in item.value for item in page.markdown)

    page.button(key="cv_analyze").click().run()

    assert not page.exception
    analysis_mock.assert_called_once()
    assert analysis_mock.call_args.kwargs["document_name"] == "synthetic.pdf"
    assert any("Unverified" in heading.value for heading in page.subheader)
    assert '"unverified"' in page.json[-1].value
    page.run()
    analysis_mock.assert_called_once()  # A rerun does not send the CV again.
    assert '"Alex Example"' in page.json[-1].value


def test_replacing_upload_clears_gemini_result_and_confirmation(
    extracted_cv_page: AppTest, analysis_mock: MagicMock, make_pdf: Callable[[list[str]], bytes]
) -> None:
    page = extracted_cv_page
    page.checkbox(key="cv_gemini_consent").check().run()
    page.button(key="cv_analyze").click().run()
    assert '"Alex Example"' in page.json[-1].value

    page.file_uploader[0].upload(
        "another.pdf", make_pdf(["Another synthetic person"]), "application/pdf"
    )
    page.run()
    assert not page.json
    assert not page.text_area
    page.button[0].click().run()

    assert not page.checkbox(key="cv_gemini_consent").value
    assert page.button(key="cv_analyze").disabled
    assert not any("Professional profile" in heading.value for heading in page.subheader)
    analysis_mock.assert_called_once()


def test_gemini_error_is_displayed_without_losing_local_preview(
    extracted_cv_page: AppTest, analysis_mock: MagicMock
) -> None:
    analysis_mock.side_effect = gemini_extraction.GeminiExtractionError(
        "Set AURA_GEMINI_API_KEY in your local .env before Gemini analysis."
    )
    page = extracted_cv_page
    page.checkbox(key="cv_gemini_consent").check().run()
    page.button(key="cv_analyze").click().run()

    assert not page.exception
    assert "AURA_GEMINI_API_KEY" in page.error[0].value
    assert page.text_area[0].value == "Alex Example"
    assert not any("Professional profile" in heading.value for heading in page.subheader)
