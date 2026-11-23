"""Real LangGraph execution with scripted model responses, not a live AI benchmark."""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langsmith import get_tracing_context

from aura.agent import CareerAgentError, CareerAssistant
from aura.core.config import Settings
from aura.schemas.job import JobInput
from aura.services.job_retrieval import JobRetrievalError, RetrievedJob


def read_sources():
    return AIMessage(
        content="",
        tool_calls=[
            {"name": "extract_cv_text", "args": {}, "id": "cv-call"},
            {"name": "job_posting_tool", "args": {}, "id": "job-call"},
        ],
    )


class ScriptedModel:
    """Only the model boundary is scripted; actual tools and graph still execute."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.seen = []
        self.tools = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        assert get_tracing_context()["enabled"] is False
        self.seen.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def agent_factory(make_pdf):
    agents = []

    def create(responses, *, jobs=None, job_retriever=None, **settings):
        model = ScriptedModel(responses)
        agent = CareerAssistant(
            make_pdf(["Alex Example\nPython developer\nBuilt a test suite"]),
            "Python required. Kubernetes preferred." if jobs is None else None,
            jobs=jobs,
            job_retriever=job_retriever,
            settings=Settings(_env_file=None, **settings),
            consent_to_send=True,
            model=model,
        )
        agents.append(agent)
        return agent, model

    yield create
    for agent in agents:
        agent.close()


def test_cv_job_assessment_and_followup_reuse_real_tool_evidence(agent_factory):
    answer = "Strength: Python (CV page 1). Kubernetes is not demonstrated, not a proven absence."
    agent, model = agent_factory(
        [
            read_sources(),
            AIMessage(answer),
            AIMessage("Emphasize the test suite already in CV page 1."),
        ]
    )

    assert agent.ask("Compare my CV with the supplied job.") == answer
    tool_messages = [m for m in model.seen[1] if isinstance(m, ToolMessage)]
    evidence = {m.name: json.loads(m.content) for m in tool_messages}
    assert "Python developer" in evidence["extract_cv_text"]["pages"][0]["text"]
    assert "Kubernetes preferred" in evidence["job_posting_tool"]["jobs"][0]["text"]
    assert agent.ask("How should I improve my CV?").startswith("Emphasize")
    assert len(model.seen) == 3
    assert any(isinstance(m, AIMessage) and m.content == answer for m in model.seen[2])
    assert sum(isinstance(m, HumanMessage) for m in model.seen[2]) == 2


def test_sequential_tool_calls_work(agent_factory):
    calls = read_sources().tool_calls
    agent, model = agent_factory(
        [
            AIMessage("", tool_calls=[calls[0]]),
            AIMessage("", tool_calls=[calls[1]]),
            AIMessage("Fit"),
        ]
    )
    assert agent.ask("Compare") == "Fit"
    assert len(model.seen) == 3


def test_conversations_have_unique_threads_and_no_shared_evidence(agent_factory):
    first, _ = agent_factory([read_sources(), AIMessage("First private answer")])
    second, model = agent_factory([read_sources(), AIMessage("Second answer")])
    first.ask("A private first-session question")
    second.ask("Compare")
    assert first._thread_id != second._thread_id
    assert "first-session" not in str(model.seen)
    assert "First private answer" not in str(model.seen)


def test_reset_deletes_checkpoints_and_requires_fresh_tool_evidence(agent_factory):
    agent, model = agent_factory([read_sources(), AIMessage("First answer")])
    agent.ask("Old question")
    old_thread = agent._thread_id
    agent.reset()
    assert list(agent._memory.list({"configurable": {"thread_id": old_thread}})) == []
    model.responses.extend([read_sources(), AIMessage("Fresh answer")])
    assert agent.ask("New question") == "Fresh answer"
    assert "Old question" not in str(model.seen[2])
    assert agent._thread_id != old_thread


def test_answer_without_both_sources_is_rejected(agent_factory):
    agent, _ = agent_factory([AIMessage("Unfounded assessment")])
    with pytest.raises(CareerAgentError, match="did not read both sources"):
        agent.ask("Compare")


def test_model_call_limit_and_failure_requires_reset(agent_factory):
    call = read_sources().tool_calls[0]
    agent, model = agent_factory([AIMessage("", tool_calls=[call])] * 3, agent_max_model_calls=2)
    with pytest.raises(CareerAgentError, match="model-call limit"):
        agent.ask("Compare")
    assert len(model.seen) == 2
    with pytest.raises(CareerAgentError, match="previous turn failed"):
        agent.ask("Retry")
    assert len(model.seen) == 2
    agent.reset()
    model.responses = [read_sources(), AIMessage("Recovered")]
    assert agent.ask("Compare") == "Recovered"


def test_tool_call_limit(agent_factory):
    agent, model = agent_factory([read_sources()] * 3)
    with pytest.raises(CareerAgentError, match="tool-call limit"):
        agent.ask("Compare")
    assert len(model.seen) == 3


@pytest.mark.parametrize(
    "calls",
    [
        [{"name": "read_local_file", "args": {}, "id": "bad"}],
        [{"name": "extract_cv_text", "args": {"file_path": "private.pdf"}, "id": "bad"}],
        [{"name": "job_posting_tool", "args": {"url": "http://localhost"}, "id": "bad"}],
    ],
)
def test_unsupported_tool_names_and_arguments_rejected(agent_factory, calls):
    agent, _ = agent_factory([AIMessage("", tool_calls=calls)])
    with pytest.raises(CareerAgentError, match="unsupported tool"):
        agent.ask("Compare")


@pytest.mark.parametrize("finish_reason", ["MAX_TOKENS", "SAFETY", "RECITATION"])
def test_incomplete_or_blocked_model_output_rejected(agent_factory, finish_reason):
    agent, _ = agent_factory(
        [read_sources(), AIMessage("partial", response_metadata={"finish_reason": finish_reason})]
    )
    with pytest.raises(CareerAgentError, match="incomplete or blocked"):
        agent.ask("Compare")


def test_empty_final_answer_rejected(agent_factory):
    agent, _ = agent_factory([read_sources(), AIMessage("")])
    with pytest.raises(CareerAgentError, match="no assessment"):
        agent.ask("Compare")


def test_turn_limit_and_reset(agent_factory):
    agent, model = agent_factory([read_sources(), AIMessage("Answer")], agent_max_turns=1)
    agent.ask("Compare")
    with pytest.raises(CareerAgentError, match="turn limit"):
        agent.ask("Another question")
    assert len(model.seen) == 2
    agent.reset()
    model.responses.extend([read_sources(), AIMessage("New answer")])
    assert agent.ask("Compare") == "New answer"


@pytest.mark.parametrize("question", ["", "   ", "x" * 4001, None])
def test_invalid_question_makes_no_model_call(agent_factory, question):
    agent, model = agent_factory([])
    with pytest.raises(CareerAgentError):
        agent.ask(question)
    assert model.seen == []


def test_external_consent_required_before_configuration(make_pdf):
    model = ScriptedModel([])
    with pytest.raises(CareerAgentError, match="Confirm external processing"):
        CareerAssistant(
            make_pdf(["Synthetic CV"]), "Job", settings=Settings(_env_file=None), model=model
        )
    assert model.tools == []


def test_provider_error_is_safe_and_not_retried(agent_factory, caplog):
    marker = "SYNTHETIC_PRIVATE_CV_OR_KEY"
    agent, model = agent_factory([RuntimeError(marker)])
    with pytest.raises(CareerAgentError, match="request failed") as failure:
        agent.ask("Compare")
    assert marker not in str(failure.value)
    assert marker not in caplog.text
    assert len(model.seen) == 1


def test_close_deletes_memory_and_prevents_more_requests(agent_factory):
    agent, _ = agent_factory([read_sources(), AIMessage("Answer")])
    agent.ask("Compare")
    thread = agent._thread_id
    agent.close()
    agent.close()
    assert list(agent._memory.list({"configurable": {"thread_id": thread}})) == []
    with pytest.raises(CareerAgentError, match="closed"):
        agent.ask("Follow-up")


def test_ambient_tracing_stays_disabled(agent_factory, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    agent, _ = agent_factory([read_sources(), AIMessage("Answer")])
    assert agent.ask("Compare") == "Answer"  # ScriptedModel asserts tracing context is off.


def test_multiple_jobs_and_followup_preserve_separate_evidence(agent_factory):
    def fetch(url):
        return RetrievedJob("Python required", url, "json_ld_job_posting")

    agent, model = agent_factory(
        [
            read_sources(),
            AIMessage("job_1: Python fit; job_2: SQL not demonstrated."),
            AIMessage("job_2 requires SQL; job_1 requires Python."),
        ],
        jobs=[
            JobInput(url="https://jobs.example.test/python"),
            JobInput(description="SQL required"),
        ],
        job_retriever=fetch,
    )
    assert "job_1" in agent.ask("Compare both jobs")
    message = next(
        m for m in model.seen[1] if isinstance(m, ToolMessage) and m.name == "job_posting_tool"
    )
    jobs = json.loads(message.content)["jobs"]
    assert jobs[0]["text"] == "Python required" and jobs[1]["text"] == "SQL required"
    assert jobs[0]["source"] == "job_url" and jobs[1]["source"] == "pasted_job"
    assert "job_2 requires SQL" in agent.ask("Which job requires SQL?")


def test_all_unavailable_jobs_require_pasted_descriptions(agent_factory):
    def fetch(_):
        raise JobRetrievalError("Website inaccessible. Paste the description instead.")

    agent, model = agent_factory(
        [read_sources(), AIMessage("An unsupported assessment must not be displayed.")],
        jobs=[JobInput(url="https://jobs.example.test/blocked")],
        job_retriever=fetch,
    )
    with pytest.raises(CareerAgentError, match="Supply pasted descriptions"):
        agent.ask("Compare")
    assert len(model.seen) == 1  # No further paid reasoning call when every source failed.
