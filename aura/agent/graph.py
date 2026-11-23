"""Explicit assistant/tools loop and isolated, bounded in-memory conversation."""

from typing import Protocol
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langsmith import tracing_context

from aura.agent.model import create_agent_model
from aura.agent.tools import AgentInputError, create_tools
from aura.core.config import Settings
from aura.prompts.career_agent_v1 import SYSTEM_PROMPT

MAX_QUESTION_CHARACTERS = 4_000
MAX_TOOL_CALLS_PER_TURN = 4


class CareerAgentError(ValueError):
    """A safe explanation; raw provider responses and CV content are never included."""


class BoundModel(Protocol):
    def invoke(self, messages: list[BaseMessage]) -> AIMessage: ...


class ToolCallingModel(Protocol):
    def bind_tools(self, tools: list[BaseTool]) -> BoundModel: ...


class AgentState(MessagesState):
    model_calls: int
    tool_calls: int


class CareerAssistant:
    """One conversation over fixed evidence. Create a new instance when inputs change.

    The caller must obtain permission before enabling external processing. A model
    can be injected for offline tests. Tracing stays disabled until the tracing task.
    Use one instance per session; concurrent calls on the same instance are unsupported.
    """

    def __init__(
        self,
        cv_pdf: bytes,
        job_description: str,
        *,
        settings: Settings,
        consent_to_send: bool = False,
        model: ToolCallingModel | None = None,
    ) -> None:
        if consent_to_send is not True:
            raise CareerAgentError("Confirm external processing before creating the career agent.")
        self._owned_model = None
        try:
            tools = create_tools(cv_pdf, job_description, max_size_mb=settings.pdf_max_size_mb)
            if model is None:
                self._owned_model = create_agent_model(settings)
                model = self._owned_model
            bound_model = model.bind_tools(tools)
        except AgentInputError as error:
            raise CareerAgentError(str(error)) from None
        except Exception:
            self.close()
            raise CareerAgentError(
                "Could not configure the agent. Check the PDF, AURA_GEMINI_API_KEY, "
                "AURA_AGENT_MODEL, and Gemini Developer API settings."
            ) from None

        self._max_model_calls = settings.agent_max_model_calls
        self._max_turns = settings.agent_max_turns
        self._turns = 0
        self._failed = False
        self._closed = False
        self._thread_id = str(uuid4())
        self._memory = InMemorySaver()
        tool_names = {tool.name for tool in tools}

        def assistant(state: AgentState) -> dict:
            if state["model_calls"] >= self._max_model_calls:
                raise CareerAgentError(
                    "The agent reached its model-call limit. Reset to try again."
                )
            response = bound_model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
            if not isinstance(response, AIMessage) or response.invalid_tool_calls:
                raise CareerAgentError(
                    "The model returned an invalid agent response. Reset to retry."
                )
            # Provider IDs are not graph identity: a repeated ID must not replace
            # an earlier message and accidentally end the tool loop.
            response = response.model_copy(update={"id": str(uuid4())})
            finish = response.response_metadata.get("finish_reason")
            if finish is not None and str(finish).upper() != "STOP":
                raise CareerAgentError(
                    "The model response was incomplete or blocked. Reset to retry."
                )
            calls = response.tool_calls
            if len(calls) > 2 or state["tool_calls"] + len(calls) > MAX_TOOL_CALLS_PER_TURN:
                raise CareerAgentError("The agent reached its tool-call limit. Reset to try again.")
            if any(call["name"] not in tool_names or call["args"] for call in calls):
                raise CareerAgentError("The model requested an unsupported tool or arguments.")
            if not calls:
                evidence = {
                    message.name
                    for message in state["messages"]
                    if isinstance(message, ToolMessage) and message.status == "success"
                }
                if not tool_names <= evidence:
                    raise CareerAgentError("The model did not read both sources. Reset to retry.")
                if not response.text.strip():
                    raise CareerAgentError("The model returned no assessment. Reset to retry.")
            return {
                "messages": [response],
                "model_calls": state["model_calls"] + 1,
                "tool_calls": state["tool_calls"] + len(calls),
            }

        builder = StateGraph(AgentState)
        builder.add_node("assistant", assistant)
        builder.add_node("tools", ToolNode(tools, handle_tool_errors=False))
        builder.add_edge(START, "assistant")
        builder.add_conditional_edges("assistant", tools_condition)
        builder.add_edge("tools", "assistant")
        self._graph = builder.compile(checkpointer=self._memory)

    def ask(self, question: str) -> str:
        """Advance one conversation turn; no automatic retries after a failure."""
        if self._closed:
            raise CareerAgentError("This agent is closed. Create a new conversation.")
        if not isinstance(question, str) or not question.strip():
            raise CareerAgentError("Enter a non-empty career question.")
        if len(question) > MAX_QUESTION_CHARACTERS:
            raise CareerAgentError("The question is too long for this prototype.")
        if self._failed:
            raise CareerAgentError("The previous turn failed. Reset before another request.")
        if self._turns >= self._max_turns:
            raise CareerAgentError("The conversation reached its turn limit. Reset to continue.")
        try:
            # Even an ambient LANGSMITH_TRACING=true must not upload private evidence.
            with tracing_context(enabled=False):
                result = self._graph.invoke(
                    {
                        "messages": [HumanMessage(question.strip())],
                        "model_calls": 0,
                        "tool_calls": 0,
                    },
                    config={
                        "configurable": {"thread_id": self._thread_id},
                        "recursion_limit": self._max_model_calls * 2 + 2,
                    },
                )
            final = result["messages"][-1]
            if not isinstance(final, AIMessage) or final.tool_calls or not final.text.strip():
                raise CareerAgentError("The agent did not finish its assessment. Reset to retry.")
            self._turns += 1
            return final.text
        except CareerAgentError:
            self._failed = True
            raise
        except Exception:
            self._failed = True
            raise CareerAgentError(
                "The agent request failed. Check model access, quota, and connection, then reset."
            ) from None

    def reset(self) -> None:
        """Release checkpoints and start a new conversation over the same evidence."""
        if self._closed:
            raise CareerAgentError("This agent is closed. Create a new conversation.")
        self._memory.delete_thread(self._thread_id)
        self._thread_id = str(uuid4())
        self._turns = 0
        self._failed = False

    def close(self) -> None:
        """Release model connections and in-memory checkpoints; safe to repeat."""
        if getattr(self, "_closed", False):
            return
        self._closed = True
        if hasattr(self, "_memory"):
            self._memory.delete_thread(self._thread_id)
        if self._owned_model is not None:
            self._owned_model.client.close()
            self._owned_model = None
        self._graph = None
