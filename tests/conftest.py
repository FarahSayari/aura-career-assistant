"""Small synthetic documents shared by service and Streamlit tests."""

import os
import socket
from collections.abc import Callable

import httpx
import langchain_google_genai.chat_models as google_chat
import pymupdf
import pytest
from google import genai

from aura.agent import model as agent_model
from aura.core.config import Settings


@pytest.fixture(autouse=True)
def isolate_agent_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never use a developer's Aura settings or ambient Google backend selection."""
    for name in os.environ:
        if name.upper().startswith("AURA_") or name in {
            "GOOGLE_GENAI_USE_VERTEXAI",
            "GOOGLE_GENAI_USE_ENTERPRISE",
        }:
            monkeypatch.delenv(name)
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture(autouse=True)
def prevent_live_web_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retrieval tests must provide fake DNS and a mock transport, never public requests."""

    def blocked(*args, **kwargs):
        pytest.fail("Live HTTP/DNS is forbidden in automated tests; provide a mock.")

    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


@pytest.fixture(autouse=True)
def prevent_live_gemini_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must explicitly substitute a mocked client; developer API keys are never used."""

    def blocked_client(*args, **kwargs):
        pytest.fail("Live Gemini clients are forbidden in automated tests; provide a mock.")

    monkeypatch.setattr(genai, "Client", blocked_client)
    # LangChain imports an SDK alias; guard that boundary and our model factory too.
    monkeypatch.setattr(google_chat, "Client", blocked_client)
    monkeypatch.setattr(agent_model, "ChatGoogleGenerativeAI", blocked_client)


@pytest.fixture
def make_pdf() -> Callable[[list[str]], bytes]:
    def build(page_texts: list[str]) -> bytes:
        with pymupdf.open() as document:
            for text in page_texts:
                page = document.new_page()
                if text:
                    page.insert_text((72, 72), text)
            document.set_metadata({"title": "Synthetic CV", "author": "Synthetic Person"})
            return document.tobytes()

    return build
