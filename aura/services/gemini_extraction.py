"""The single external boundary for opt-in Gemini CV analysis; never logs request/response data."""

import json

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from aura.core.config import Settings
from aura.prompts.cv_extraction_v1 import SYSTEM_PROMPT
from aura.schemas.cv_extraction import CvExtraction
from aura.schemas.professional_profile import ProfessionalProfile
from aura.services.pdf_extraction import ExtractedPdf
from aura.services.profile_conversion import to_professional_profile


class GeminiExtractionError(ValueError):
    """An expected extraction failure with a predefined, non-sensitive UI message."""


def _api_error_message(code: int | None) -> str:
    if code in (401, 403):
        return "Gemini access was denied. Check your API key and project permissions."
    if code == 404:
        return (
            "The configured Gemini model is unavailable. Set AURA_GEMINI_MODEL to an enabled model."
        )
    if code == 400:
        return (
            "Gemini rejected the request. Check the API key, configured model, "
            "and structured-output support."
        )
    if code == 429:
        return "Gemini rate limit or quota exceeded. Check your quota and try again later."
    if code in (408, 504):
        return "Gemini timed out. No automatic retry was made; try again when ready."
    if code is not None and code >= 500:
        return "Gemini is temporarily unavailable. No automatic retry was made; try again later."
    return "Gemini could not process the request. Check your configuration and try again later."


def extract_cv_profile(
    document: ExtractedPdf, *, settings: Settings, document_name: str
) -> ProfessionalProfile:
    """After caller consent, make one request and return a validated, unverified profile."""
    if not document.text.strip():
        raise GeminiExtractionError(
            "There is no extracted CV text to analyze. Extract PDF text first."
        )
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
        raise GeminiExtractionError(
            "Set AURA_GEMINI_API_KEY in your local .env before Gemini analysis."
        )
    if not settings.gemini_model.strip():
        raise GeminiExtractionError(
            "Set AURA_GEMINI_MODEL to a model enabled for your Gemini API project."
        )
    contents = json.dumps(
        {
            "pages": [
                {
                    "page_number": page.page_number,
                    "layout_warning": page.layout_warning,
                    "blocks": [{"text": block.text, "bbox": block.bbox} for block in page.blocks],
                }
                for page in document.pages
            ]
        },
        ensure_ascii=False,
    )
    try:
        with genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            vertexai=False,
            enterprise=False,
            http_options=types.HttpOptions(
                timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        ) as client:
            response = client.models.generate_content(
                model=settings.gemini_model.strip(),
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_json_schema=CvExtraction.model_json_schema(),
                    temperature=0,
                    max_output_tokens=8192,
                ),
            )
    except errors.APIError as error:
        raise GeminiExtractionError(_api_error_message(error.code)) from None
    except (httpx.TimeoutException, TimeoutError):
        raise GeminiExtractionError(
            "Gemini timed out. No automatic retry was made; try again when ready."
        ) from None
    except (httpx.TransportError, ConnectionError, OSError):
        raise GeminiExtractionError(
            "Could not connect to Gemini. Check your network and try again."
        ) from None
    except Exception:
        # Third-party errors may embed credentials or CV content. Never expose their details.
        raise GeminiExtractionError(
            "Gemini analysis failed. Check your configuration and try again."
        ) from None

    if not response.candidates or len(response.candidates) != 1:
        raise GeminiExtractionError(
            "Gemini returned no usable extraction. The request may have been blocked."
        )
    if response.candidates[0].finish_reason != types.FinishReason.STOP:
        raise GeminiExtractionError(
            "Gemini returned an incomplete or blocked response. No profile was accepted."
        )
    try:
        extraction = CvExtraction.model_validate_json(response.text or "")
        return to_professional_profile(
            extraction, document_name=document_name, page_count=document.page_count
        )
    except (ValidationError, ValueError):
        raise GeminiExtractionError(
            "Gemini returned invalid structured CV data. No profile was accepted; "
            "review the CV text and retry if needed."
        ) from None
