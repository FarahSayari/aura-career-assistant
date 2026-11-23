"""Verify Gemini configuration and actual request serialization over local HTTP only."""

import json
from unittest.mock import MagicMock

import httpx
import langchain_google_genai.chat_models as google_chat
import pytest
from google.genai import Client as SdkClient
from langchain_google_genai import ChatGoogleGenerativeAI

from aura.agent import CareerAgentError, CareerAssistant
from aura.agent import model as agent_model
from aura.core.config import Settings


def test_factory_uses_explicit_candidate_and_disables_retries(monkeypatch):
    constructor = MagicMock()
    monkeypatch.setattr(agent_model, "ChatGoogleGenerativeAI", constructor)
    settings = Settings(
        _env_file=None, gemini_api_key="synthetic-key", agent_model="candidate-model"
    )
    agent_model.create_agent_model(settings)
    args = constructor.call_args.kwargs
    assert args["model"] == "candidate-model"
    assert args["api_key"].get_secret_value() == "synthetic-key"
    assert args["vertexai"] is False
    assert args["max_retries"] == 0
    assert args["timeout"] == 60
    assert args["cache"] is False


def test_missing_credentials_rejected_without_sdk_construction():
    with pytest.raises(ValueError, match="AURA_GEMINI_API_KEY"):
        agent_model.create_agent_model(Settings(_env_file=None))


@pytest.mark.parametrize("switch", ["GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_ENTERPRISE"])
def test_ambient_backends_do_not_switch_provider(monkeypatch, switch):
    monkeypatch.setenv(switch, "true")
    with pytest.raises(ValueError, match="backend switches"):
        agent_model.create_agent_model(Settings(_env_file=None, gemini_api_key="synthetic-key"))


@pytest.mark.parametrize("http_status", [200, 429])
def test_real_adapter_cv_tools_and_followup_over_mock_http(monkeypatch, make_pdf, http_status):
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if http_status == 429:
            return httpx.Response(
                429, json={"error": {"code": 429, "message": "SYNTHETIC_PRIVATE_PROVIDER_DETAIL"}}
            )
        assert "candidate-model:generateContent" in str(request.url)
        assert body["generationConfig"]["maxOutputTokens"] == 2048
        if len(requests) == 1:
            declarations = body["tools"][0]["functionDeclarations"]
            assert {tool["name"] for tool in declarations} == {
                "extract_cv_text",
                "job_posting_tool",
            }
            parts = [
                {"functionCall": {"name": name, "args": {}}}
                for name in ("extract_cv_text", "job_posting_tool")
            ]
        else:
            assert "Synthetic Python CV" in json.dumps(body)
            assert "Python required" in json.dumps(body)
            parts = [{"text": "Python is supported by CV page 1 and required by the pasted job."}]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}
                ]
            },
        )

    monkeypatch.setenv("GOOGLE_GENAI_HTTP_CLIENT", "httpx")

    def factory(**kwargs):
        options = kwargs["http_options"].model_copy(
            update={"httpx_client": httpx.Client(transport=httpx.MockTransport(handler))}
        )
        return SdkClient(**{**kwargs, "http_options": options}, vertexai=False, enterprise=False)

    monkeypatch.setattr(google_chat, "Client", factory)
    monkeypatch.setattr(agent_model, "ChatGoogleGenerativeAI", ChatGoogleGenerativeAI)
    agent = CareerAssistant(
        make_pdf(["Synthetic Python CV"]),
        "Python required",
        settings=Settings(
            _env_file=None, gemini_api_key="synthetic-key", agent_model="candidate-model"
        ),
        consent_to_send=True,
    )
    try:
        if http_status == 429:
            with pytest.raises(CareerAgentError, match="request failed") as failure:
                agent.ask("Compare")
            assert "PRIVATE_PROVIDER_DETAIL" not in str(failure.value)
            assert len(requests) == 1
        else:
            assert "CV page 1" in agent.ask("Compare")
            assert "CV page 1" in agent.ask("Why?")
            assert len(requests) == 3
    finally:
        agent.close()
