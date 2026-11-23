"""One explicitly configured Gemini model; no calls happen on import."""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

from aura.core.config import Settings


def create_agent_model(settings: Settings) -> ChatGoogleGenerativeAI:
    """Construct the candidate model without invoking it or choosing another provider."""
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
        raise ValueError("Set AURA_GEMINI_API_KEY before running the career agent.")
    if not settings.agent_model.strip():
        raise ValueError("Set AURA_AGENT_MODEL to a tool-calling model enabled for your project.")
    # The integration's underlying SDK can read these ambient backend switches.
    if any(
        os.getenv(name, "").lower() in {"true", "1"}
        for name in ("GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_ENTERPRISE")
    ):
        raise ValueError("Disable ambient Google backend switches to use the Gemini Developer API.")
    return ChatGoogleGenerativeAI(
        model=settings.agent_model.strip(),
        api_key=settings.gemini_api_key,
        vertexai=False,
        temperature=0,
        max_output_tokens=2048,
        timeout=60,
        max_retries=0,
        include_thoughts=False,
        cache=False,
    )
