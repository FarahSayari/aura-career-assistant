"""Offline Gemini contracts: synthetic CVs, mocked SDK responses, and local HTTP transport."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from google import genai
from google.genai import errors, types
from google.genai.client import Client as SdkClient
from pydantic import BaseModel, ValidationError

from aura.core.config import Settings
from aura.prompts.cv_extraction_v1 import PROMPT_VERSION, SYSTEM_PROMPT
from aura.schemas.cv_extraction import CvExtraction
from aura.schemas.professional_profile import EvidenceRecord, ProfessionalProfile
from aura.services.gemini_extraction import GeminiExtractionError, extract_cv_profile
from aura.services.pdf_extraction import ExtractedPdf, PdfPage, PdfTextBlock
from aura.services.profile_conversion import to_professional_profile

BASELINE = json.loads(
    (Path(__file__).resolve().parents[1] / "evals" / "cv_extraction_baseline.json").read_text(
        "utf-8"
    )
)


def document_from_text(text: str) -> ExtractedPdf:
    return ExtractedPdf(
        (PdfPage(1, 600, 800, (PdfTextBlock(text, (40, 40, 550, 300), 0),)),), {}, 1000, False
    )


def sdk_response(text: str, finish_reason=types.FinishReason.STOP) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(parts=[types.Part(text=text)]), finish_reason=finish_reason
            )
        ]
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gemini_api_key="synthetic-api-key", gemini_model="gemini-2.5-flash", _env_file=None
    )


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    factory = MagicMock()
    factory.return_value.__enter__.return_value.models.generate_content.return_value = sdk_response(
        "{}"
    )
    monkeypatch.setattr(genai, "Client", factory)
    return factory


def all_records(value: object):
    if isinstance(value, EvidenceRecord):
        yield value
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            if name not in {"sources", "verification_status"}:
                yield from all_records(getattr(value, name))
    elif isinstance(value, list):
        for item in value:
            yield from all_records(item)


@pytest.mark.parametrize("case", BASELINE["cases"], ids=lambda case: case["id"])
def test_baseline_structured_extraction(case: dict, settings: Settings, sdk: MagicMock) -> None:
    generate = sdk.return_value.__enter__.return_value.models.generate_content
    generate.return_value = sdk_response(json.dumps(case["expected_extraction"]))

    profile = extract_cv_profile(
        document_from_text(case["cv_text"]), settings=settings, document_name="synthetic-cv.pdf"
    )

    expected = ProfessionalProfile.model_validate(case["expected_extraction"])
    profile_facts = profile.model_dump(mode="json")

    # Compare professional facts independently of the application-owned provenance below.
    def without_provenance(value):
        if isinstance(value, dict):
            return {
                k: without_provenance(v)
                for k, v in value.items()
                if k not in {"sources", "verification_status"}
            }
        if isinstance(value, list):
            return [without_provenance(item) for item in value]
        return value

    assert without_provenance(profile_facts) == without_provenance(expected.model_dump(mode="json"))
    assert profile.career_preferences is None
    for record in all_records(profile):
        assert record.verification_status.value == "unverified"
        assert len(record.sources) == 1
        assert record.sources[0].source_type.value == "cv"
        assert record.sources[0].reference == "synthetic-cv.pdf"
        assert "page-level attribution not resolved" in record.sources[0].locator
    assert ProfessionalProfile.model_validate_json(profile.model_dump_json()) == profile
    generate.assert_called_once()
    request = generate.call_args.kwargs
    assert json.loads(request["contents"])["pages"][0]["blocks"][0]["text"] == case["cv_text"]
    assert "synthetic-cv.pdf" not in request["contents"]
    assert request["config"].response_mime_type == "application/json"
    assert request["config"].response_json_schema == CvExtraction.model_json_schema()
    assert request["config"].system_instruction == SYSTEM_PROMPT
    assert BASELINE["prompt_version"] == PROMPT_VERSION
    assert sdk.call_args.kwargs["http_options"].retry_options.attempts == 1
    assert sdk.call_args.kwargs["http_options"].timeout == 60_000
    assert sdk.call_args.kwargs["vertexai"] is False
    sdk.return_value.__exit__.assert_called_once()


def test_missing_optional_facts_remain_unknown() -> None:
    profile = to_professional_profile(CvExtraction(), document_name="synthetic.pdf", page_count=2)

    assert profile.identity.full_name is None
    assert profile.identity.contact is None
    assert profile.professional_summary is None
    assert profile.career_preferences is None
    assert profile.projects == []
    assert "1–2" in profile.identity.sources[0].locator


def test_mixed_features_and_partial_dates_are_preserved() -> None:
    extraction = CvExtraction.model_validate(BASELINE["cases"][2]["expected_extraction"])
    profile = to_professional_profile(extraction, document_name="synthetic.pdf", page_count=1)

    assert len(profile.work_experience) == 2
    assert len(profile.projects) == 2
    assert profile.work_experience[0].dates.start.day is None
    assert profile.work_experience[1].dates.start.month is None
    assert profile.work_experience[1].dates.is_current is True
    assert [feature.status.value for feature in profile.projects[0].features] == [
        "completed",
        "planned",
        "unknown",
    ]
    assert profile.projects[1].features[0].status.value == "in_progress"
    assert profile.technical_skills == []  # Project technologies do not manufacture skill records.


@pytest.mark.parametrize(
    "payload",
    [
        {"verification_status": "verified"},
        {"sources": [{"source_type": "manual", "reference": "Trusted"}]},
        {"career_preferences": {"work_modes": ["remote"]}},
        {"identity": {"full_name": "Alex", "verification_status": "verified"}},
        {"identity": {"contact": {"email": "alex@example.com", "sources": []}}},
        {
            "projects": [
                {
                    "name": "Demo",
                    "features": [{"name": "Search", "verification_status": "verified"}],
                }
            ]
        },
    ],
)
def test_model_cannot_supply_trust_metadata_or_preferences(payload: dict) -> None:
    with pytest.raises(ValidationError):
        CvExtraction.model_validate(payload)


def test_structured_output_schema_has_no_trust_or_preference_fields() -> None:
    schema = CvExtraction.model_json_schema()
    for definition in [schema, *schema["$defs"].values()]:
        assert (
            not {"sources", "verification_status", "career_preferences"}
            & definition.get("properties", {}).keys()
        )


@pytest.mark.parametrize(
    "text",
    [
        "not JSON",
        "[]",
        "null",
        '{"projects": "not a list"}',
        '{"projects": [{"name": "Demo", "status": "invented"}]}',
        '{"education": [{"dates": {"start": {"year": 2023, "month": 2, "day": 29}}}]}',
        '{"projects": [{"name": "Demo", "status": "planned", '
        '"achievements": ["Already delivered"]}]}',
        '{"certifications": [{"name": "Demo", "url": "not-a-url"}]}',
        '{"career_preferences": {"target_roles": ["CEO"]}}',
    ],
)
def test_invalid_json_and_semantic_validation_fail_safely(
    text: str, settings: Settings, sdk: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    sdk.return_value.__enter__.return_value.models.generate_content.return_value = sdk_response(
        text
    )

    with pytest.raises(GeminiExtractionError, match="invalid structured CV data") as failure:
        extract_cv_profile(
            document_from_text("Synthetic CV"), settings=settings, document_name="synthetic.pdf"
        )

    assert text not in str(failure.value)
    assert text not in caplog.text


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("gemini_api_key", None, "AURA_GEMINI_API_KEY"),
        ("gemini_api_key", "   ", "AURA_GEMINI_API_KEY"),
        ("gemini_model", "   ", "AURA_GEMINI_MODEL"),
    ],
)
def test_missing_configuration_prevents_request(field, value, message, settings, sdk) -> None:
    settings = Settings(**{**settings.model_dump(), field: value}, _env_file=None)
    with pytest.raises(GeminiExtractionError, match=message):
        extract_cv_profile(
            document_from_text("Synthetic CV"), settings=settings, document_name="synthetic.pdf"
        )
    sdk.assert_not_called()


def test_empty_cv_text_prevents_request(settings: Settings, sdk: MagicMock) -> None:
    with pytest.raises(GeminiExtractionError, match="no extracted CV text"):
        extract_cv_profile(
            document_from_text("   \n"), settings=settings, document_name="synthetic.pdf"
        )
    sdk.assert_not_called()


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (400, "rejected the request"),
        (401, "access was denied"),
        (403, "access was denied"),
        (404, "model is unavailable"),
        (408, "timed out"),
        (429, "quota exceeded"),
        (500, "temporarily unavailable"),
        (504, "timed out"),
        (418, "could not process"),
    ],
)
def test_api_errors_are_safe_and_not_retried(code, message, settings, sdk, caplog) -> None:
    private_marker = "SYNTHETIC_SECRET_OR_CV_FRAGMENT"
    generate = sdk.return_value.__enter__.return_value.models.generate_content
    generate.side_effect = errors.APIError(code, {"error": {"message": private_marker}})

    with pytest.raises(GeminiExtractionError, match=message) as failure:
        extract_cv_profile(
            document_from_text(private_marker), settings=settings, document_name="synthetic.pdf"
        )

    assert private_marker not in str(failure.value)
    assert private_marker not in caplog.text
    generate.assert_called_once()
    sdk.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (httpx.ReadTimeout("synthetic-sensitive-data"), "timed out"),
        (httpx.ConnectError("synthetic-sensitive-data"), "Could not connect"),
        (RuntimeError("synthetic-sensitive-data"), "analysis failed"),
    ],
)
def test_transport_errors_do_not_expose_raw_details(error, message, settings, sdk) -> None:
    sdk.return_value.__enter__.return_value.models.generate_content.side_effect = error
    with pytest.raises(GeminiExtractionError, match=message) as failure:
        extract_cv_profile(
            document_from_text("Synthetic CV"), settings=settings, document_name="synthetic.pdf"
        )
    assert "synthetic-sensitive-data" not in str(failure.value)


@pytest.mark.parametrize(
    "finish_reason", [types.FinishReason.MAX_TOKENS, types.FinishReason.SAFETY]
)
def test_incomplete_or_blocked_responses_are_not_accepted(finish_reason, settings, sdk) -> None:
    sdk.return_value.__enter__.return_value.models.generate_content.return_value = sdk_response(
        "{}", finish_reason
    )
    with pytest.raises(GeminiExtractionError, match="incomplete or blocked"):
        extract_cv_profile(
            document_from_text("Synthetic CV"), settings=settings, document_name="synthetic.pdf"
        )


def test_no_candidates_returns_useful_error(settings, sdk) -> None:
    sdk.return_value.__enter__.return_value.models.generate_content.return_value = (
        types.GenerateContentResponse()
    )
    with pytest.raises(GeminiExtractionError, match="no usable extraction"):
        extract_cv_profile(
            document_from_text("Synthetic CV"), settings=settings, document_name="synthetic.pdf"
        )


def test_real_sdk_serializes_schema_using_mock_http_transport(monkeypatch, settings) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["responseJsonSchema"]["type"] == "object"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": '{"identity":{"full_name":"Alex Example"}}'}],
                        },
                        "finishReason": "STOP",
                    }
                ]
            },
        )

    monkeypatch.setenv("GOOGLE_GENAI_HTTP_CLIENT", "httpx")

    def factory(**kwargs):
        options = kwargs["http_options"].model_copy(
            update={"httpx_client": httpx.Client(transport=httpx.MockTransport(handler))}
        )
        return SdkClient(**{**kwargs, "http_options": options})

    monkeypatch.setattr(genai, "Client", factory)
    profile = extract_cv_profile(
        document_from_text("Alex Example"), settings=settings, document_name="synthetic.pdf"
    )

    assert len(requests) == 1
    assert profile.identity.full_name == "Alex Example"
    assert profile.identity.verification_status.value == "unverified"
