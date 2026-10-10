"""Module 5 AI Agent Engineering demonstration (Story 10, M5-D01/M5-D02).

Run from the repository root:

    uv run streamlit run module-05/app.py

One Streamlit page with the four frozen demonstration areas: Autonomous Agent,
Memory, Tool Integrations and Reliability. Every action runs the accepted
``ai_agent_engineering`` components: the lifecycle-owning ReAct runner, the
allowlisted ``ToolRegistry``, the native and Mem0-adapter memory, the
LangChain/OpenAI/Anthropic integrations, and the resilience primitives.

This file is a presentation layer. The only logic it adds is demonstration
stand-ins for things that would otherwise need a remote model or service: a
keyword planner that proposes tool calls, scripted provider responses served
to the real SDKs through in-process mock transports, a scripted LangChain chat
model, and an in-process backend for the Mem0 adapter. Every stand-in is
labelled on the page. The public UI starts zero-key and may retain explicitly
authorized OpenAI or Anthropic credentials only in Streamlit session state.
PR-01 does not use those credentials for provider calls; live execution is
introduced only by the separately verified live-provider stories.

Trust boundaries: the goal, memory text, tool output and provider output are
untrusted data. They are rendered only through ``st.text``, ``st.code``,
``st.json`` and ``st.dataframe``; app-owned guidance is the only Markdown.
Proposed tool calls execute only through ``ToolRegistry``.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import httpx  # noqa: E402
import httpx2  # noqa: E402
import streamlit as st  # noqa: E402
from ai_agent_engineering.agent.react import (  # noqa: E402
    AgentDecision,
    DecisionKind,
    DecisionRecord,
)
from ai_agent_engineering.agent.runner import (  # noqa: E402
    AgentExecutionError,
    DecisionProvider,
    run_agent,
)
from ai_agent_engineering.integrations import (  # noqa: E402
    build_langchain_agent,
    invoke_langchain_agent,
)
from ai_agent_engineering.memory import (  # noqa: E402
    Episode,
    EpisodicMemory,
    LongTermMemory,
    Mem0IntegrationError,
    Mem0MemoryAdapter,
    ShortTermMemory,
)
from ai_agent_engineering.models import AgentRunState, AgentStatus  # noqa: E402
from ai_agent_engineering.providers import (  # noqa: E402
    AnthropicToolLoopBudgetError,
    AnthropicToolUseError,
    OpenAIToolCallError,
    OpenAIToolLoopBudgetError,
    anthropic_tools,
    response_tools,
    run_anthropic_tool_use,
    run_openai_function_calling,
)
from ai_agent_engineering.resilience import (  # noqa: E402
    OperationTimeoutError,
    RetryExhaustedError,
    run_with_fallback,
    run_with_retry,
    run_with_timeout,
)
from ai_agent_engineering.tools import (  # noqa: E402
    ToolAuthorizationError,
    ToolRegistry,
    ToolValidationError,
    UnknownToolError,
    build_default_registry,
)
from anthropic import Anthropic  # noqa: E402
from langchain_core.callbacks.manager import CallbackManagerForLLMRun  # noqa: E402
from langchain_core.language_models.chat_models import (  # noqa: E402
    BaseChatModel,
    LangSmithParams,
)
from langchain_core.language_models.fake_chat_models import (  # noqa: E402
    FakeListChatModel,
)
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from langsmith import tracing_context  # noqa: E402
from openai import OpenAI  # noqa: E402

# ---------------------------------------------------------------------------
# Evidence labels. Each demonstration states which of these it produces.
# ---------------------------------------------------------------------------

EVIDENCE_DETERMINISTIC = "Deterministic local execution of accepted Module 5 code"
EVIDENCE_MOCKED = (
    "Mocked transport: the real SDK serializes requests and parses scripted "
    "responses in-process. No network. Not live provider evidence."
)
EVIDENCE_LANGCHAIN = (
    "Genuine LangChain create_agent runtime driven by a local scripted chat "
    "model. No LLM is called."
)
EVIDENCE_STAND_IN = (
    "Real Mem0MemoryAdapter over a local in-process stand-in backend. "
    "This is not the Mem0 library."
)
EVIDENCE_GENUINE_MEM0 = (
    "Genuine local Mem0: the real mem0 library (Memory.from_config) behind "
    "the accepted Mem0MemoryAdapter, with local Qdrant, a cached local Hugging "
    "Face embedder, a local fake LangChain LLM, telemetry off and the Hugging "
    "Face hub offline. Not remote or cloud Mem0."
)
EVIDENCE_LIVE = (
    "Live provider execution is opt-in and potentially billable. OpenAI and "
    "Anthropic live execution paths are implemented, but a run is labelled LIVE "
    "evidence only after the explicitly user-initiated provider workflow succeeds. "
    "Deterministic mocked-transport demos remain available."
)
OPENAI_LIVE_MODEL = "gpt-5.6-terra"
OPENAI_LIVE_MAX_REQUESTS = 3
OPENAI_LIVE_MAX_TOOL_CALLS = 4
OPENAI_LIVE_TIMEOUT_SECONDS = 20.0

ANTHROPIC_LIVE_MODEL = "claude-sonnet-5-5"
ANTHROPIC_LIVE_MAX_REQUESTS = 3
ANTHROPIC_LIVE_MAX_TOOL_CALLS = 4
ANTHROPIC_LIVE_MAX_OUTPUT_TOKENS = 1024
ANTHROPIC_LIVE_TIMEOUT_SECONDS = 20.0

PROVIDER_CREDENTIALS = {
    "OpenAI": {
        "service_name": "openai",
        "session_input_key": "credential_openai",
        "session_authorized_key": "authorized_openai_api_key",
    },
    "Anthropic": {
        "service_name": "anthropic",
        "session_input_key": "credential_anthropic",
        "session_authorized_key": "authorized_anthropic_api_key",
    },
}


def authorized_session_key(provider_name: str) -> str | None:
    """Return an explicitly authorized session credential for a provider.

    Args:
        provider_name: Application-owned provider label.

    Returns:
        The authorized session credential when present, otherwise ``None``.

    Raises:
        ValueError: If the provider is not application allowlisted.
    """
    config = PROVIDER_CREDENTIALS.get(provider_name)
    if config is None:
        raise ValueError(f"Unsupported provider: {provider_name}")

    value = st.session_state.get(config["session_authorized_key"])
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    return stripped or None


def authorize_entered_keys() -> None:
    """Authorize entered provider credentials for this Streamlit session only."""
    authorized: list[str] = []

    for provider_name, config in PROVIDER_CREDENTIALS.items():
        entered = st.session_state.get(config["session_input_key"], "")
        value = entered.strip() if isinstance(entered, str) else ""

        if value:
            st.session_state[config["session_authorized_key"]] = value
            authorized.append(provider_name)

        # Do not retain a second plaintext copy in the input widget state.
        st.session_state[config["session_input_key"]] = ""

    if authorized:
        st.session_state["credential_notice"] = (
            "Authorized for this browser session: " + ", ".join(authorized) + "."
        )
        st.session_state["credential_notice_type"] = "success"
    else:
        st.session_state["credential_notice"] = (
            "No API keys were entered. Existing authorized session credentials "
            "were left unchanged."
        )
        st.session_state["credential_notice_type"] = "warning"


def clear_authorized_credentials() -> None:
    """Remove all provider credentials retained by the current Streamlit session."""
    for config in PROVIDER_CREDENTIALS.values():
        st.session_state.pop(config["session_authorized_key"], None)
        st.session_state[config["session_input_key"]] = ""

    st.session_state["credential_notice"] = (
        "All authorized session credentials were cleared."
    )
    st.session_state["credential_notice_type"] = "success"

AREAS = ("Autonomous Agent", "Memory", "Tool Integrations", "Reliability")

COVERAGE = (
    ("M5-L01", "Lab: Build tool-using AI agent", "Autonomous Agent > Run agent"),
    (
        "M5-L02",
        "Lab: Implement memory-enabled workflows",
        "Autonomous Agent (memory on) + Memory",
    ),
    (
        "M5-L03",
        "Lab: Create multi-step reasoning systems",
        "Autonomous Agent > multi-step goal",
    ),
    (
        "M5-L04",
        "Lab: Build retry/fallback mechanisms",
        "Reliability > any scenario",
    ),
    (
        "M5-D01",
        "Deliverable: Autonomous AI agent",
        "Autonomous Agent > Run agent",
    ),
    (
        "M5-D02",
        "Deliverable: Stateful workflow system",
        "Autonomous Agent > workflow state + Memory",
    ),
)

GOAL_PRESETS = {
    "Multi-step: explain ReAct, then calculate 6 times 7": (
        "Explain ReAct and calculate 6 times 7"
    ),
    "Three tools: agent lifecycle, 15 plus 27, safety note": (
        "Explain the agent lifecycle, calculate 15 plus 27, "
        "and check the safety note"
    ),
    "Single tool: calculate 120 divided by 4": "Calculate 120 divided by 4",
    "Context: retrieve the safety rule note": "Retrieve the safety rule note",
    "No matching tool: write a poem": "Write a poem about the sea",
}

MAX_GOAL_CHARS = 300
MAX_PLANNED_CALLS = 4

# ---------------------------------------------------------------------------
# Demonstration planner: a deterministic stand-in for a model that proposes
# tool calls. Its proposals are untrusted and pass through ToolRegistry.
# ---------------------------------------------------------------------------

_TOPICS = ("react", "tool schema", "agent lifecycle")
_OPERATIONS = (
    ("add", ("plus", "add", "sum")),
    ("subtract", ("minus", "subtract")),
    ("multiply", ("times", "multiply", "multiplied", "product")),
    ("divide", ("divide", "divided")),
)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True, slots=True)
class PlannedCall:
    """One tool call proposed by the demonstration planner."""

    tool_name: str
    arguments: dict[str, Any]
    rationale: str


def _has_word(text: str, words: Sequence[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def plan_tool_calls(goal: str) -> tuple[PlannedCall, ...]:
    """Propose an ordered, bounded list of tool calls for a goal.

    Args:
        goal: Untrusted goal text.

    Returns:
        Proposed calls, at most ``MAX_PLANNED_CALLS``; empty when no
        allowlisted tool matches.
    """
    text = goal.casefold()
    calls: list[PlannedCall] = []

    for topic in _TOPICS:
        if topic in text:
            calls.append(
                PlannedCall(
                    "knowledge_lookup",
                    {"topic": topic},
                    f"Look up '{topic}' in bounded local knowledge.",
                )
            )

    numbers = _NUMBER.findall(text)
    operation = next(
        (name for name, words in _OPERATIONS if _has_word(text, words)),
        None,
    )
    if operation is not None and len(numbers) >= 2:
        calls.append(
            PlannedCall(
                "calculator",
                {
                    "operation": operation,
                    "left": float(numbers[0]),
                    "right": float(numbers[1]),
                },
                f"Use the calculator to {operation} the two numbers in the goal.",
            )
        )

    if _has_word(text, ("note", "safety", "rule")):
        calls.append(
            PlannedCall(
                "note_lookup",
                {"key": "safety_rule"},
                "Retrieve the structured safety note.",
            )
        )

    return tuple(calls[:MAX_PLANNED_CALLS])


def build_plan_decider(
    plan: Sequence[PlannedCall],
    *,
    prior_outcome: str | None = None,
) -> DecisionProvider:
    """Turn a plan into a ReAct decision provider for ``run_agent``.

    Each decision is chosen from the observations already in application
    state: one planned tool per step, then an explicit finish.
    """

    def decide(state: AgentRunState) -> AgentDecision:
        done = len(state.observations)
        if done < len(plan):
            call = plan[done]
            return AgentDecision(
                kind=DecisionKind.TOOL,
                rationale=call.rationale,
                tool_name=call.tool_name,
                arguments=dict(call.arguments),
            )

        if not plan:
            summary = "No allowlisted tool matches this goal; no tool was run."
        else:
            parts = [
                f"{item['tool']} -> {json.dumps(item['result'])}"
                for item in state.observations
            ]
            summary = "Completed with observations: " + "; ".join(parts)

        if prior_outcome is not None:
            summary += f" (Prior episode for this goal: {prior_outcome})"

        return AgentDecision(
            kind=DecisionKind.FINISH,
            rationale=(
                "Every planned step has an observation."
                if plan
                else "No allowlisted tool applies, so finish explicitly."
            ),
            final_result=summary,
        )

    return decide


# ---------------------------------------------------------------------------
# Memory bundle (native memory + Mem0 adapter), kept in session state.
# ---------------------------------------------------------------------------


class LocalMem0StandIn:
    """In-process backend satisfying the ``Mem0Backend`` protocol.

    It exists so the real ``Mem0MemoryAdapter`` can be exercised on a zero-key
    page. It is not the Mem0 library: search is plain word overlap scoped by
    the ``user_id`` filter.
    """

    def __init__(self) -> None:
        self._rows: list[dict[str, str]] = []

    def add(self, messages: list[dict[str, str]], *, user_id: str) -> Any:
        results = []
        for message in messages:
            row = {
                "id": f"local-{len(self._rows) + 1}",
                "memory": message["content"],
                "user_id": user_id,
            }
            self._rows.append(row)
            results.append({"id": row["id"], "memory": row["memory"], "event": "ADD"})
        return {"results": results}

    def search(self, query: str, *, filters: dict[str, Any]) -> Any:
        words = set(query.casefold().split())
        results = []
        for row in self._rows:
            if row["user_id"] != filters.get("user_id"):
                continue
            overlap = len(words & set(row["memory"].casefold().split()))
            if overlap:
                results.append(
                    {
                        "id": row["id"],
                        "memory": row["memory"],
                        "score": overlap / len(words),
                    }
                )
        results.sort(key=lambda item: item["score"], reverse=True)
        return {"results": results}


MEM0_USERS = ("demo-user-a", "demo-user-b")

# Genuine local Mem0 reuses Story 5's path: the mem0ai 2.2.1 overlay that
# `uv run --with` cached, run offline. It is not a project dependency. The
# file watcher is off because it imports every transformers submodule.
GENUINE_MEM0_LAUNCH = (
    "$env:MEM0_TELEMETRY='False'; $env:HF_HUB_OFFLINE='1'; "
    "uv run --offline --no-sync --with mem0ai==2.2.1 "
    "streamlit run module-05/app.py --server.fileWatcherType none"
)
GENUINE_MEM0_EMBEDDER = "sentence-transformers/all-MiniLM-L6-v2"
GENUINE_MEM0_DIMS = 384


def genuine_mem0_readiness() -> tuple[bool, str]:
    """Check that the real Mem0 library can run here offline.

    Importing mem0 makes no network call. The checks read the settings the
    libraries themselves resolved; no credential or variable is read here.

    Returns:
        Whether the genuine path may start, and the reason.
    """
    if find_spec("mem0") is None:
        return False, "The mem0 library is not installed in this environment."
    if import_module("mem0.memory.telemetry").MEM0_TELEMETRY:
        return False, "Mem0 telemetry is on; it would send events to PostHog."
    if not import_module("huggingface_hub.constants").HF_HUB_OFFLINE:
        return False, "The Hugging Face hub is online; the embedder could contact it."
    return True, "mem0 is installed, its telemetry is off and the hub is offline."


class NoInferMem0:
    """Pass-through to a real ``mem0.Memory`` that stores text verbatim.

    ``infer=False`` skips LLM fact extraction, exactly as Story 5's genuine run
    did, so no model is asked to rewrite memories.
    """

    def __init__(self, memory: Any) -> None:
        self.memory = memory

    def add(self, messages: list[dict[str, str]], *, user_id: str) -> Any:
        return self.memory.add(messages, user_id=user_id, infer=False)

    def search(self, query: str, *, filters: dict[str, Any]) -> Any:
        return self.memory.search(query, filters=filters)


@dataclass
class GenuineMem0:
    """The accepted adapter over a real, local ``mem0.Memory``."""

    adapter: Mem0MemoryAdapter
    memory: Any
    version: str
    store: Path


def build_genuine_mem0(store: Path | None = None) -> GenuineMem0:
    """Start the real Mem0 library with local-only components.

    Args:
        store: App-owned directory for Qdrant and history; a new temporary
            directory when omitted. It is never taken from user input.

    Raises:
        Mem0IntegrationError: If the offline preconditions fail or Mem0
            cannot start.
    """
    ready, reason = genuine_mem0_readiness()
    if not ready:
        raise Mem0IntegrationError(reason)

    mem0 = import_module("mem0")
    store = store or Path(tempfile.mkdtemp(prefix="module5-mem0-"))
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "module5_demo",
                "path": str(store / "qdrant"),
                "embedding_model_dims": GENUINE_MEM0_DIMS,
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": GENUINE_MEM0_EMBEDDER,
                "embedding_dims": GENUINE_MEM0_DIMS,
            },
        },
        "llm": {
            "provider": "langchain",
            "config": {"model": FakeListChatModel(responses=["{}"])},
        },
        "history_db_path": str(store / "history.db"),
    }
    try:
        memory = mem0.Memory.from_config(config)
    except Exception as exc:
        raise Mem0IntegrationError("Genuine local Mem0 could not start.") from exc

    return GenuineMem0(
        adapter=Mem0MemoryAdapter(NoInferMem0(memory)),
        memory=memory,
        version=str(mem0.__version__),
        store=store,
    )


@dataclass
class MemoryBundle:
    """The accepted memory components shared across reruns of one session."""

    short_term: ShortTermMemory = field(
        default_factory=lambda: ShortTermMemory(max_items=12)
    )
    long_term: LongTermMemory = field(default_factory=LongTermMemory)
    episodic: EpisodicMemory = field(
        default_factory=lambda: EpisodicMemory(max_episodes=20)
    )
    mem0: Mem0MemoryAdapter = field(
        default_factory=lambda: Mem0MemoryAdapter(LocalMem0StandIn())
    )


# ---------------------------------------------------------------------------
# Autonomous agent run with an application-observed lifecycle trace.
# ---------------------------------------------------------------------------

# Proposals the authority boundary rejects before any handler runs.
AUTHORITY_ERRORS = (UnknownToolError, ToolValidationError, ToolAuthorizationError)
# Everything a run may stop on without crashing the page: denials plus a
# tool that fails at runtime (for example division by zero).
DENIAL_ERRORS = (*AUTHORITY_ERRORS, AgentExecutionError, ValueError)


@dataclass
class AgentDemoRun:
    """Everything one agent run exposes to the page."""

    state: AgentRunState
    records: tuple[DecisionRecord, ...]
    trace: list[dict[str, Any]]
    executed: list[str]
    loaded_context: dict[str, Any]
    error: str | None = None
    denied: bool = False


def observed_registry(
    on_execute: Callable[[str], None],
) -> ToolRegistry:
    """Build the default allowlist with handlers that report execution.

    The definitions, schemas and authorization flags are the accepted ones;
    only the handler is wrapped so the page can observe real executions.
    """

    def wrap(definition: Any) -> Any:
        def handler(arguments: Any) -> Any:
            on_execute(definition.name)
            return definition.handler(arguments)

        return replace(definition, handler=handler)

    return ToolRegistry(
        wrap(definition) for definition in build_default_registry().definitions()
    )


def _load_memory_context(state: AgentRunState, memory: MemoryBundle) -> dict[str, Any]:
    facts = memory.long_term.snapshot()
    state.retrieved_long_term_memories = [
        {"key": key, "content": content} for key, content in facts.items()
    ]
    state.short_term_context = {
        "recent_context": list(memory.short_term.recall()),
        "recent_episodes": [
            {"goal": episode.goal, "outcome": episode.outcome}
            for episode in memory.episodic.recent(3)
        ],
    }
    return {
        "long_term_facts": state.retrieved_long_term_memories,
        **state.short_term_context,
    }


def _prior_outcome(goal: str, memory: MemoryBundle | None) -> str | None:
    if memory is None:
        return None
    matches = [
        episode
        for episode in memory.episodic.recent()
        if episode.goal.casefold() == goal.strip().casefold()
    ]
    return matches[-1].outcome if matches else None


def run_autonomous_agent(
    goal: str,
    *,
    max_steps: int = 6,
    memory: MemoryBundle | None = None,
    decide: DecisionProvider | None = None,
) -> AgentDemoRun:
    """Run the accepted bounded ReAct runner and capture visible evidence.

    Args:
        goal: Untrusted goal text.
        max_steps: Application-owned execution budget.
        memory: When given, context is loaded into state before the run and
            the run is written back to short-term and episodic memory.
        decide: Optional decision provider; defaults to the planner.

    Raises:
        ValueError: If the goal is empty (raised by ``AgentRunState``).
    """
    state = AgentRunState(goal=goal[:MAX_GOAL_CHARS], max_steps=max_steps)
    trace: list[dict[str, Any]] = [
        {"step": 0, "observed_status": state.status.value, "event": "goal received"}
    ]
    executed: list[str] = []
    seen: list[DecisionRecord] = []

    loaded = _load_memory_context(state, memory) if memory is not None else {}
    if decide is None:
        decide = build_plan_decider(
            plan_tool_calls(state.goal),
            prior_outcome=_prior_outcome(state.goal, memory),
        )

    def on_execute(name: str) -> None:
        executed.append(name)
        trace.append(
            {
                "step": state.current_step,
                "observed_status": state.status.value,
                "event": f"validated call executing: {name}",
            }
        )

    def traced_decide(current: AgentRunState) -> AgentDecision:
        decision = decide(current)
        trace.append(
            {
                "step": current.current_step + 1,
                "observed_status": current.status.value,
                "event": (
                    f"decision: {decision.kind.value}"
                    + (f" -> {decision.tool_name}" if decision.tool_name else "")
                ),
            }
        )
        seen.append(
            DecisionRecord(
                step=current.current_step + 1,
                kind=decision.kind,
                rationale=decision.rationale,
                tool_name=decision.tool_name,
            )
        )
        return decision

    error: str | None = None
    denied = False
    records: tuple[DecisionRecord, ...]
    try:
        state, records = run_agent(state, observed_registry(on_execute), traced_decide)
    except DENIAL_ERRORS as exc:
        error = f"{type(exc).__name__}: {exc}"
        denied = isinstance(exc, AUTHORITY_ERRORS)
        records = tuple(seen)

    trace.append(
        {
            "step": state.current_step,
            "observed_status": state.status.value,
            "event": "terminal" if state.is_terminal else "stopped (fail closed)",
        }
    )

    if memory is not None:
        memory.short_term.remember(f"goal: {state.goal}")
        for item in state.observations:
            memory.short_term.remember(f"{item['tool']}: {json.dumps(item['result'])}")
        outcome = state.status.value
        if error is not None:
            outcome = f"stopped at {outcome}: {error}"
        elif state.terminal_failure:
            outcome = f"{outcome}: {state.terminal_failure}"
        memory.episodic.remember(
            Episode(goal=state.goal, outcome=outcome, tools=tuple(state.selected_tools))
        )

    return AgentDemoRun(
        state=state,
        records=records,
        trace=trace,
        executed=executed,
        loaded_context=loaded,
        error=error,
        denied=denied,
    )


def workflow_snapshot(state: AgentRunState) -> dict[str, Any]:
    """Project the application-owned workflow state for display."""
    return {
        "run_id": state.run_id,
        "goal": state.goal,
        "status": state.status.value,
        "is_terminal": state.is_terminal,
        "current_step": state.current_step,
        "max_steps": state.max_steps,
        "steps_remaining": state.steps_remaining,
        "selected_tools": list(state.selected_tools),
        "observations": list(state.observations),
        "retrieved_long_term_memories": list(state.retrieved_long_term_memories),
        "short_term_context": dict(state.short_term_context),
        "retry_count": state.retry_count,
        "fallback_history": list(state.fallback_history),
        "final_result": state.final_result,
        "terminal_failure": state.terminal_failure,
    }


# ---------------------------------------------------------------------------
# Tool integrations: LangChain, OpenAI and Anthropic, all offline.
# ---------------------------------------------------------------------------

DEFAULT_CALL = PlannedCall(
    "calculator",
    {"operation": "multiply", "left": 6.0, "right": 7.0},
    "Default calculator call.",
)
HOSTILE_CALL = PlannedCall(
    "shell",
    {"command": "whoami"},
    "Hostile provider proposal: an invented tool.",
)
OPENAI_MOCK_BASE_URL = "https://openai-mock.invalid/v1"
ANTHROPIC_MOCK_BASE_URL = "https://anthropic-mock.invalid"
MOCK_API_KEY = "mock-key-not-a-credential"


@dataclass
class IntegrationDemo:
    """Visible evidence from one integration run."""

    integration: str
    evidence: str
    tools_sent: list[Any]
    requests: list[Any]
    executed: list[str]
    output_text: str = ""
    error: str | None = None


def _provider_calls(goal: str, hostile: bool) -> list[PlannedCall]:
    calls = list(plan_tool_calls(goal)) or [DEFAULT_CALL]
    if hostile:
        calls.append(HOSTILE_CALL)
    return calls


class ScriptedToolCallingModel(BaseChatModel):
    """Local LangChain chat model that proposes one planned call per turn."""

    planned_calls: list[dict[str, Any]] = []

    @property
    def _llm_type(self) -> str:
        return "module-05-scripted-tool-calling-model"

    def _get_ls_params(
        self,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LangSmithParams:
        return LangSmithParams(
            ls_provider="module-05-local",
            ls_model_name="scripted",
            ls_model_type="chat",
        )

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        del tools, kwargs
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if len(results) < len(self.planned_calls):
            call = self.planned_calls[len(results)]
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": call["name"],
                        "args": call["args"],
                        "id": f"lc-call-{len(results) + 1}",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            message = AIMessage(
                content="Scripted summary of LangChain tool results: "
                + " | ".join(str(m.content) for m in results)
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


def run_langchain_demo(goal: str) -> IntegrationDemo:
    """Run the accepted LangChain agent integration with a scripted model."""
    executed: list[str] = []
    registry = observed_registry(executed.append)
    calls = list(plan_tool_calls(goal)) or [DEFAULT_CALL]
    model = ScriptedToolCallingModel(
        planned_calls=[{"name": c.tool_name, "args": c.arguments} for c in calls]
    )
    demo = IntegrationDemo(
        integration="LangChain Agents",
        evidence=EVIDENCE_LANGCHAIN,
        tools_sent=list(registry.names()),
        requests=[],
        executed=executed,
    )
    with tracing_context(enabled=False):
        agent = build_langchain_agent(model=model, registry=registry)
        result = invoke_langchain_agent(agent, goal=goal)

    for message in result["messages"]:
        demo.requests.append(
            {
                "message": type(message).__name__,
                "content": str(message.content),
                "tool_calls": [
                    {"name": c["name"], "args": c["args"]}
                    for c in getattr(message, "tool_calls", [])
                ],
            }
        )
    demo.output_text = str(result["messages"][-1].content)
    return demo


def _openai_client(
    first_calls: list[PlannedCall],
    requests: list[Any],
) -> OpenAI:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if "previous_response_id" not in body:
            output = [
                {
                    "type": "function_call",
                    "id": f"fc-{index}",
                    "call_id": f"call-{index}",
                    "name": call.tool_name,
                    "arguments": json.dumps(call.arguments),
                    "status": "completed",
                }
                for index, call in enumerate(first_calls, start=1)
            ]
        else:
            outputs = [item["output"] for item in body["input"]]
            output = [
                {
                    "type": "message",
                    "id": "msg-final",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Scripted summary of tool outputs: "
                            + "; ".join(outputs),
                            "annotations": [],
                        }
                    ],
                }
            ]
        return httpx.Response(
            200,
            json={
                "id": f"resp-{len(requests)}",
                "object": "response",
                "created_at": 0,
                "model": "mock-model",
                "status": "completed",
                "output": output,
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "tools": [],
            },
        )

    return OpenAI(
        api_key=MOCK_API_KEY,
        base_url=OPENAI_MOCK_BASE_URL,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def run_openai_demo(goal: str, *, hostile: bool = False) -> IntegrationDemo:
    """Run the accepted OpenAI function-calling loop over a mock transport."""
    executed: list[str] = []
    registry = observed_registry(executed.append)
    demo = IntegrationDemo(
        integration="OpenAI Function Calling",
        evidence=EVIDENCE_MOCKED,
        tools_sent=list(response_tools(registry)),
        requests=[],
        executed=executed,
    )
    client = _openai_client(_provider_calls(goal, hostile), demo.requests)
    try:
        result = run_openai_function_calling(
            client,
            registry,
            model="mock-model",
            user_input=goal,
            max_requests=3,
            max_tool_calls=MAX_PLANNED_CALLS + 1,
        )
        demo.output_text = result.output_text
    except (
        *DENIAL_ERRORS,
        OpenAIToolCallError,
        OpenAIToolLoopBudgetError,
    ) as exc:
        demo.error = f"{type(exc).__name__}: {exc}"
    return demo



def run_openai_live(goal: str, *, api_key: str) -> IntegrationDemo:
    """Run one explicitly authorized, bounded live OpenAI tool-use workflow.

    The credential is supplied by the Streamlit session caller and is used only
    to construct the OpenAI client for this invocation. Provider output remains
    untrusted and every proposed tool call must pass through the application-
    owned ToolRegistry before execution.

    Args:
        goal: User goal sent to the live OpenAI Responses API.
        api_key: Explicitly authorized session credential.

    Returns:
        Visible integration evidence with the provider result or a sanitized
        failure classification.

    Raises:
        ValueError: If the goal or credential is empty.
    """
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("The live OpenAI goal must not be empty.")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("OpenAI has no authorized session credential.")

    executed: list[str] = []
    registry = observed_registry(executed.append)
    demo = IntegrationDemo(
        integration="OpenAI Function Calling - LIVE",
        evidence=(
            "OpenAI live mode was explicitly requested. Successful LIVE provider "
            "evidence has not yet been established for this run."
        ),
        tools_sent=list(response_tools(registry)),
        requests=[],
        executed=executed,
    )

    try:
        client = OpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=OPENAI_LIVE_TIMEOUT_SECONDS,
        )
        result = run_openai_function_calling(
            client,
            registry,
            model=OPENAI_LIVE_MODEL,
            user_input=goal,
            max_requests=OPENAI_LIVE_MAX_REQUESTS,
            max_tool_calls=OPENAI_LIVE_MAX_TOOL_CALLS,
        )
        demo.output_text = result.output_text
        demo.evidence = (
            "LIVE OpenAI evidence: a real user-initiated provider workflow "
            "completed successfully through the bounded application-owned "
            "ToolRegistry path."
        )
    except (
        *DENIAL_ERRORS,
        OpenAIToolCallError,
        OpenAIToolLoopBudgetError,
    ) as exc:
        demo.error = (
            f"{type(exc).__name__}: request stopped by application controls."
        )
    except Exception as exc:
        # Remote exception text is deliberately not reflected into the UI.
        # Provider errors may contain sensitive request metadata.
        demo.error = f"{type(exc).__name__}: live OpenAI request failed safely."

    return demo
def run_anthropic_live(goal: str, *, api_key: str) -> IntegrationDemo:
    """Run one explicitly authorized bounded Anthropic live workflow.

    Args:
        goal: Untrusted user goal supplied to the provider workflow.
        api_key: Session-only credential explicitly authorized by the user.

    Returns:
        Integration evidence with provider output and allowlisted tool records.

    Raises:
        ValueError: If the goal or authorized credential is empty.
    """
    if not goal.strip():
        raise ValueError("A non-empty goal is required for Anthropic live execution.")
    if not api_key.strip():
        raise ValueError(
            "An explicitly authorized Anthropic session credential is required."
        )

    executed: list[str] = []
    registry = observed_registry(executed.append)
    demo = IntegrationDemo(
        integration="Anthropic Tool Use - LIVE",
        evidence=(
            "Anthropic live mode was explicitly requested. Successful LIVE provider "
            "evidence has not yet been established for this run."
        ),
        output_text="",
        requests=[],
        executed=executed,
        tools_sent=registry.names(),
    )

    try:
        client = Anthropic(
            api_key=api_key,
            max_retries=0,
            timeout=ANTHROPIC_LIVE_TIMEOUT_SECONDS,
        )
        result = run_anthropic_tool_use(
            client,
            registry,
            model=ANTHROPIC_LIVE_MODEL,
            user_input=goal,
            max_tokens=ANTHROPIC_LIVE_MAX_OUTPUT_TOKENS,
            max_requests=ANTHROPIC_LIVE_MAX_REQUESTS,
            max_tool_calls=ANTHROPIC_LIVE_MAX_TOOL_CALLS,
        )
        demo.output_text = result.output_text
        demo.evidence = (
            "LIVE Anthropic evidence: a real user-initiated provider workflow "
            "completed successfully through the bounded application-owned "
            "ToolRegistry path."
        )
    except (UnknownToolError, ToolValidationError) as exc:
        demo.error = f"{type(exc).__name__}: tool proposal denied safely."
    except Exception as exc:
        # Remote exception text is deliberately excluded from the UI because
        # provider errors may contain sensitive request metadata.
        demo.error = f"{type(exc).__name__}: live Anthropic request failed safely."

    return demo

def _anthropic_client(
    first_calls: list[PlannedCall],
    requests: list[Any],
) -> Anthropic:
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        requests.append(body)
        if len(body["messages"]) == 1:
            content = [
                {
                    "type": "tool_use",
                    "id": f"toolu_demo_{index}",
                    "name": call.tool_name,
                    "input": call.arguments,
                }
                for index, call in enumerate(first_calls, start=1)
            ]
            stop_reason = "tool_use"
        else:
            outputs = [block["content"] for block in body["messages"][-1]["content"]]
            content = [
                {
                    "type": "text",
                    "text": "Scripted summary of tool results: " + "; ".join(outputs),
                }
            ]
            stop_reason = "end_turn"
        return httpx2.Response(
            200,
            json={
                "id": f"msg_demo_{len(requests)}",
                "type": "message",
                "role": "assistant",
                "model": "mock-model",
                "content": content,
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    return Anthropic(
        api_key=MOCK_API_KEY,
        base_url=ANTHROPIC_MOCK_BASE_URL,
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def run_anthropic_demo(goal: str, *, hostile: bool = False) -> IntegrationDemo:
    """Run the accepted Anthropic tool-use loop over a mock transport."""
    executed: list[str] = []
    registry = observed_registry(executed.append)
    demo = IntegrationDemo(
        integration="Anthropic Tool Use",
        evidence=EVIDENCE_MOCKED,
        tools_sent=list(anthropic_tools(registry)),
        requests=[],
        executed=executed,
    )
    client = _anthropic_client(_provider_calls(goal, hostile), demo.requests)
    try:
        result = run_anthropic_tool_use(
            client,
            registry,
            model="mock-model",
            user_input=goal,
            max_tokens=256,
            max_requests=3,
            max_tool_calls=MAX_PLANNED_CALLS + 1,
        )
        demo.output_text = result.output_text
    except (
        *DENIAL_ERRORS,
        AnthropicToolUseError,
        AnthropicToolLoopBudgetError,
    ) as exc:
        demo.error = f"{type(exc).__name__}: {exc}"
    return demo


# ---------------------------------------------------------------------------
# Reliability scenarios over the accepted resilience primitives.
# ---------------------------------------------------------------------------

SUCCESS = "Success"
RECOVERED = "Recovered"
BOUNDED_FAILURE = "Bounded failure"
DENIED = "Denied (unsafe or invalid)"


@dataclass
class ReliabilityOutcome:
    """Classified result of one reliability scenario."""

    scenario: str
    classification: str
    summary: str
    events: list[dict[str, Any]]


CALCULATOR_6X7 = {"operation": "multiply", "left": 6, "right": 7}


def _retry_recovers() -> ReliabilityOutcome:
    registry = build_default_registry()
    events: list[dict[str, Any]] = []

    def operation() -> Any:
        attempt = len(events) + 1
        if attempt <= 2:
            events.append({"attempt": attempt, "result": "ConnectionError (injected)"})
            raise ConnectionError("injected transient fault")
        result = registry.execute("calculator", CALCULATOR_6X7)
        events.append({"attempt": attempt, "result": json.dumps(result)})
        return result

    retried = run_with_retry(operation, max_attempts=3, retry_on=(ConnectionError,))
    return ReliabilityOutcome(
        "Retry recovers a transient fault",
        RECOVERED,
        f"Succeeded on attempt {retried.attempts} of 3 with {retried.value}.",
        events,
    )


def _retry_exhausted() -> ReliabilityOutcome:
    events: list[dict[str, Any]] = []

    def operation() -> Any:
        events.append(
            {"attempt": len(events) + 1, "result": "ConnectionError (injected)"}
        )
        raise ConnectionError("injected persistent fault")

    try:
        run_with_retry(operation, max_attempts=3, retry_on=(ConnectionError,))
    except RetryExhaustedError as exc:
        return ReliabilityOutcome(
            "Retry budget exhausted",
            BOUNDED_FAILURE,
            f"Stopped after {exc.attempts} attempts; the failure is reported, "
            "not converted into success.",
            events,
        )
    raise AssertionError("retry exhaustion did not occur")


def _validation_not_retried() -> ReliabilityOutcome:
    registry = build_default_registry()
    events: list[dict[str, Any]] = []

    def operation() -> Any:
        events.append({"attempt": len(events) + 1, "result": "ToolValidationError"})
        return registry.execute(
            "calculator", {"operation": "power", "left": 2, "right": 8}
        )

    try:
        run_with_retry(operation, max_attempts=3, retry_on=(ConnectionError,))
    except ToolValidationError as exc:
        return ReliabilityOutcome(
            "Invalid call is not retried",
            DENIED,
            f"Rejected on attempt 1 and never retried: {exc}",
            events,
        )
    raise AssertionError("validation failure did not occur")


def _timeout() -> ReliabilityOutcome:
    async def slow_tool() -> str:
        await asyncio.sleep(2)
        return "too late"

    try:
        asyncio.run(run_with_timeout(slow_tool(), timeout_seconds=0.05))
    except OperationTimeoutError as exc:
        return ReliabilityOutcome(
            "Timeout enforced",
            BOUNDED_FAILURE,
            f"{exc}; the slow operation was cancelled instead of hanging.",
            [{"operation": "slow_tool (2 s)", "deadline_seconds": 0.05}],
        )
    raise AssertionError("timeout did not occur")


def _within_deadline() -> ReliabilityOutcome:
    registry = build_default_registry()

    async def fast_tool() -> Any:
        return registry.execute("calculator", CALCULATOR_6X7)

    value = asyncio.run(run_with_timeout(fast_tool(), timeout_seconds=1.0))
    return ReliabilityOutcome(
        "Operation within deadline",
        SUCCESS,
        f"Finished inside the 1 s deadline with {value}.",
        [{"operation": "calculator", "deadline_seconds": 1.0}],
    )


def _fallback() -> ReliabilityOutcome:
    registry = build_default_registry()
    events: list[dict[str, Any]] = []

    def primary() -> Any:
        events.append(
            {"path": "primary (remote provider)", "result": "ConnectionError"}
        )
        raise ConnectionError("injected provider outage")

    def fallback() -> Any:
        result = registry.execute("knowledge_lookup", {"topic": "react"})
        events.append({"path": "fallback (local tool)", "result": json.dumps(result)})
        return result

    result = run_with_fallback(primary, fallback, fallback_on=(ConnectionError,))
    return ReliabilityOutcome(
        "Fallback after provider outage",
        RECOVERED,
        f"used_fallback={result.used_fallback}; "
        f"primary_error={type(result.primary_error).__name__}.",
        events,
    )


def _agent_scenario(
    name: str,
    decision: Callable[[AgentRunState], AgentDecision],
    max_steps: int,
) -> ReliabilityOutcome:
    run = run_autonomous_agent(
        "Reliability demonstration", max_steps=max_steps, decide=decision
    )
    events = [*run.trace, {"tools_executed": len(run.executed)}]
    if run.error is not None:
        return ReliabilityOutcome(
            name,
            DENIED if run.denied else BOUNDED_FAILURE,
            f"{run.error.rstrip('.')}. Tools executed: {len(run.executed)}. "
            f"Lifecycle stopped at {run.state.status.value}; no result was "
            "reported as success.",
            events,
        )
    return ReliabilityOutcome(
        name,
        BOUNDED_FAILURE,
        f"Terminal state {run.state.status.value}: {run.state.terminal_failure}",
        events,
    )


def _never_finishes(state: AgentRunState) -> AgentDecision:
    return AgentDecision(
        kind=DecisionKind.TOOL,
        rationale="Keep calculating (a decider that never finishes).",
        tool_name="calculator",
        arguments=dict(CALCULATOR_6X7),
    )


def _proposes_shell(state: AgentRunState) -> AgentDecision:
    return AgentDecision(
        kind=DecisionKind.TOOL,
        rationale="Hostile proposal: run a shell command.",
        tool_name="shell",
        arguments={"command": "whoami"},
    )


def _injects_argument(state: AgentRunState) -> AgentDecision:
    return AgentDecision(
        kind=DecisionKind.TOOL,
        rationale="Hostile proposal: smuggle an extra argument.",
        tool_name="calculator",
        arguments={**CALCULATOR_6X7, "command": "whoami"},
    )


def _divides_by_zero(state: AgentRunState) -> AgentDecision:
    return AgentDecision(
        kind=DecisionKind.TOOL,
        rationale="Valid call whose tool fails at runtime.",
        tool_name="calculator",
        arguments={"operation": "divide", "left": 1, "right": 0},
    )


RELIABILITY_SCENARIOS: dict[str, Callable[[], ReliabilityOutcome]] = {
    "Retry recovers a transient fault": _retry_recovers,
    "Retry budget exhausted": _retry_exhausted,
    "Invalid call is not retried": _validation_not_retried,
    "Timeout enforced": _timeout,
    "Operation within deadline": _within_deadline,
    "Fallback after provider outage": _fallback,
    "Execution budget exhausted": lambda: _agent_scenario(
        "Execution budget exhausted", _never_finishes, 3
    ),
    "Unknown tool denied": lambda: _agent_scenario(
        "Unknown tool denied", _proposes_shell, 3
    ),
    "Injected argument denied": lambda: _agent_scenario(
        "Injected argument denied", _injects_argument, 3
    ),
    "Tool failure fails closed": lambda: _agent_scenario(
        "Tool failure fails closed", _divides_by_zero, 3
    ),
}


def run_reliability_scenario(name: str) -> ReliabilityOutcome:
    """Run one allowlisted scenario; unknown names are rejected."""
    if name not in RELIABILITY_SCENARIOS:
        raise KeyError(f"Unknown reliability scenario: {name!r}")
    return RELIABILITY_SCENARIOS[name]()


# ---------------------------------------------------------------------------
# Page rendering.
# ---------------------------------------------------------------------------


def _guidance(do: str, expect: str, proves: str) -> None:
    st.markdown(
        f"**What to do:** {do}\n\n"
        f"**What to expect:** {expect}\n\n"
        f"**What it proves:** {proves}"
    )


def _memory() -> MemoryBundle:
    if "memory" not in st.session_state:
        st.session_state["memory"] = MemoryBundle()
    return st.session_state["memory"]


def _render_header() -> None:
    st.title("Module 5: AI Agent Engineering")
    st.caption(
        "A stateful, bounded, tool-using agent with memory and reliability "
        "controls. Every button runs the accepted Module 5 code."
    )
    st.info(EVIDENCE_LIVE)
    with st.expander("Evidence labels used on this page"):
        st.markdown(
            f"- **Deterministic:** {EVIDENCE_DETERMINISTIC}\n"
            f"- **LangChain:** {EVIDENCE_LANGCHAIN}\n"
            f"- **Mocked transport:** {EVIDENCE_MOCKED}\n"
            f"- **Mem0 stand-in:** {EVIDENCE_STAND_IN}\n"
            f"- **Live providers:** {EVIDENCE_LIVE}"
        )
    with st.expander("Where each lab and deliverable is demonstrated"):
        st.dataframe(
            [
                {"ID": code, "Requirement": name, "Where to run it": where}
                for code, name, where in COVERAGE
            ],
            hide_index=True,
        )


def _render_agent_area() -> None:
    st.header("Autonomous Agent")
    _guidance(
        "Pick a goal (or type your own), set the step budget and press Run agent.",
        "A lifecycle trace, the tools the agent selected, each validated "
        "observation, application-visible decision records and a terminal state. "
        "Lower the budget below the number of steps to see budget_exhausted.",
        "A goal-driven agent runs a bounded Reason -> Act -> Observe loop and "
        "selects tools dynamically, but every call is validated by the "
        "application allowlist before it executes (M5-L01, M5-L03, M5-D01, "
        "M5-D02).",
    )
    st.caption(
        f"{EVIDENCE_DETERMINISTIC}. Tool proposals come from a local keyword "
        "planner standing in for a model; they are untrusted and validated "
        "like any model output."
    )

    preset = st.selectbox("Goal", list(GOAL_PRESETS), key="agent_preset")
    custom = st.text_input(
        "Or type your own goal (untrusted input)",
        max_chars=MAX_GOAL_CHARS,
        key="agent_custom_goal",
    )
    max_steps = st.slider("Step budget", 1, 8, 6, key="agent_max_steps")
    use_memory = st.checkbox(
        "Use memory (load context before the run, record the run after)",
        value=True,
        key="agent_use_memory",
    )

    if st.button("Run agent", key="run_agent", type="primary"):
        goal = custom.strip() or GOAL_PRESETS[preset]
        try:
            st.session_state["agent_run"] = run_autonomous_agent(
                goal,
                max_steps=max_steps,
                memory=_memory() if use_memory else None,
            )
        except ValueError:
            st.session_state.pop("agent_run", None)
            st.error("The goal must not be empty.")

    run: AgentDemoRun | None = st.session_state.get("agent_run")
    if run is None:
        return

    state = run.state
    columns = st.columns(3)
    columns[0].metric("Terminal state", state.status.value)
    columns[1].metric(
        "Steps used / budget", f"{state.current_step} / {state.max_steps}"
    )
    columns[2].metric("Tools executed", len(run.executed))

    st.subheader("Goal")
    st.text(state.goal)
    if state.status is AgentStatus.COMPLETED:
        st.success("Completed")
        st.text(state.final_result)
    elif run.denied:
        st.error("Denied before execution: the proposal failed validation.")
        st.code(run.error, language=None)
    elif run.error is not None:
        st.warning("The tool failed at runtime; the run stopped (fail closed).")
        st.code(run.error, language=None)
    else:
        st.warning("Bounded termination")
        st.text(state.terminal_failure or state.status.value)

    st.subheader("Lifecycle trace (observed by the application)")
    st.dataframe(run.trace, hide_index=True)
    st.subheader("Decision records")
    st.caption(
        "Application-visible decision/action records only. No private "
        "chain-of-thought is produced or shown."
    )
    st.dataframe(
        [
            {
                "step": record.step,
                "kind": record.kind.value,
                "tool": record.tool_name or "",
                "rationale": record.rationale,
            }
            for record in run.records
        ],
        hide_index=True,
    )
    st.subheader("Selected tools and observations")
    st.json(
        {"selected_tools": state.selected_tools, "observations": state.observations}
    )
    if run.loaded_context:
        st.subheader("Memory context loaded into this run")
        st.json(run.loaded_context)
    with st.expander("Stateful workflow: full application-owned run state"):
        st.json(workflow_snapshot(state))


def _render_memory_area() -> None:
    memory = _memory()
    st.header("Memory")
    _guidance(
        "Run the agent twice with memory on, store a long-term fact below, and "
        "try the Mem0 adapter with two different users.",
        "Short-term context and episodes grow with each run; the next run loads "
        "facts, recent context and prior episodes into its state, and repeats "
        "of a goal report the prior episode. Mem0 recall returns only the "
        "selected user's memories.",
        "Short-term, long-term and episodic memory give context continuity "
        "across runs while remaining data with no authority (M5-L02, M5-D02).",
    )
    st.caption(f"Native Module 5 memory: {EVIDENCE_DETERMINISTIC}.")

    st.subheader("Short-term memory (current session context)")
    st.dataframe(
        [{"item": item} for item in memory.short_term.recall()], hide_index=True
    )
    if st.button("Clear short-term memory", key="clear_short_term"):
        memory.short_term.clear()
        st.rerun()

    st.subheader("Long-term memory (facts kept across runs)")
    with st.form("long_term_form", clear_on_submit=True):
        key = st.text_input("Key", max_chars=60, key="lt_key")
        content = st.text_input(
            "Fact (untrusted data)", max_chars=MAX_GOAL_CHARS, key="lt_content"
        )
        if st.form_submit_button("Remember fact", key="lt_submit"):
            try:
                memory.long_term.remember(key, content)
            except ValueError:
                st.error("Key and fact must both be non-empty.")
    st.json(memory.long_term.snapshot())

    st.subheader("Episodic memory (previous agent runs)")
    st.dataframe(
        [
            {
                "goal": episode.goal,
                "outcome": episode.outcome,
                "tools": ", ".join(episode.tools),
                "at": episode.created_at.isoformat(timespec="seconds"),
            }
            for episode in memory.episodic.recent()
        ],
        hide_index=True,
    )

    _render_genuine_mem0()

    st.subheader("Mem0 adapter demo with a local stand-in (not Mem0)")
    st.caption(EVIDENCE_STAND_IN)
    st.markdown(
        "This deterministic demo works in any environment. It exercises the "
        "adapter contract only and is not Mem0 evidence; use the genuine local "
        "Mem0 section above for that."
    )
    user = st.selectbox("Memory user", MEM0_USERS, key="mem0_user")
    note = st.text_input("Memory to add", max_chars=MAX_GOAL_CHARS, key="mem0_note")
    if st.button("Add through Mem0 adapter", key="mem0_add"):
        try:
            st.session_state["mem0_ack"] = memory.mem0.remember(
                user_id=user, content=note
            )
        except ValueError:
            st.error("Memory text must not be empty.")
    if "mem0_ack" in st.session_state:
        st.json(st.session_state["mem0_ack"])
    query = st.text_input("Recall query", max_chars=MAX_GOAL_CHARS, key="mem0_query")
    if st.button("Recall through Mem0 adapter", key="mem0_recall"):
        try:
            records = memory.mem0.recall(user_id=user, query=query)
            st.session_state["mem0_records"] = [
                {"user": user, "memory": r.content, "id": r.memory_id, "score": r.score}
                for r in records
            ]
        except (ValueError, Mem0IntegrationError):
            st.error("Recall needs a non-empty query.")
    if "mem0_records" in st.session_state:
        st.dataframe(st.session_state["mem0_records"], hide_index=True)


def _render_genuine_mem0() -> None:
    st.subheader("Mem0 integration: genuine local Mem0 library")
    st.caption(EVIDENCE_GENUINE_MEM0)
    st.markdown(
        "Press **Start genuine local Mem0**. It starts only when the page was "
        "launched in the offline Mem0 environment from Story 5; otherwise it "
        "explains why and changes nothing. Launch command:"
    )
    st.code(GENUINE_MEM0_LAUNCH, language="powershell")
    if st.button("Start genuine local Mem0", key="genuine_mem0_start"):
        try:
            st.session_state["genuine_mem0"] = build_genuine_mem0()
            st.session_state.pop("genuine_mem0_blocked", None)
        except Mem0IntegrationError as exc:
            st.session_state["genuine_mem0_blocked"] = str(exc)
    if "genuine_mem0_blocked" in st.session_state:
        st.warning("Genuine local Mem0 is not available in this launch.")
        st.text(st.session_state["genuine_mem0_blocked"])

    genuine: GenuineMem0 | None = st.session_state.get("genuine_mem0")
    if genuine is None:
        return
    memory_type = type(genuine.memory)
    st.success("Genuine local Mem0 is running.")
    st.text(
        f"Library: mem0 {genuine.version}; "
        f"object: {memory_type.__module__}.{memory_type.__qualname__}"
    )
    user = st.selectbox("Mem0 user", MEM0_USERS, key="genuine_mem0_user")
    note = st.text_input(
        "Memory to add (genuine Mem0)",
        max_chars=MAX_GOAL_CHARS,
        key="genuine_mem0_note",
    )
    if st.button("Add to genuine Mem0", key="genuine_mem0_add"):
        try:
            st.session_state["genuine_mem0_ack"] = genuine.adapter.remember(
                user_id=user, content=note
            )
        except (ValueError, Mem0IntegrationError) as exc:
            st.error(f"Not stored: {type(exc).__name__}.")
    if "genuine_mem0_ack" in st.session_state:
        st.json(st.session_state["genuine_mem0_ack"])
    query = st.text_input(
        "Recall query (genuine Mem0)",
        max_chars=MAX_GOAL_CHARS,
        key="genuine_mem0_query",
    )
    if st.button("Recall from genuine Mem0", key="genuine_mem0_recall"):
        try:
            st.session_state["genuine_mem0_records"] = [
                {"user": user, "memory": r.content, "id": r.memory_id, "score": r.score}
                for r in genuine.adapter.recall(user_id=user, query=query)
            ]
        except (ValueError, Mem0IntegrationError) as exc:
            st.error(f"Recall failed: {type(exc).__name__}.")
    if "genuine_mem0_records" in st.session_state:
        st.dataframe(st.session_state["genuine_mem0_records"], hide_index=True)


def _render_integration_result(demo: IntegrationDemo) -> None:
    st.markdown(f"**{demo.integration}**")
    st.caption(demo.evidence)
    if demo.error is not None:
        if demo.executed:
            st.error(
                "Execution stopped safely after one or more allowlisted tools ran. "
                "No further provider or tool execution was permitted."
            )
        else:
            st.error(
                "Execution stopped safely before any tool ran."
            )
        st.code(demo.error, language=None)
    else:
        st.success("Completed")
        st.text(demo.output_text)
    st.metric("Tools executed through ToolRegistry", len(demo.executed))
    st.json({"executed": demo.executed})
    with st.expander("Tool schemas sent (from the registry allowlist)"):
        st.json(demo.tools_sent)
    if demo.integration == "LangChain Agents":
        label = "Agent messages"
    elif demo.integration.endswith("- LIVE"):
        label = "Live request evidence"
    else:
        label = "Exact request bodies the SDK sent (to the mock transport)"
    with st.expander(label):
        if demo.integration.endswith("- LIVE"):
            st.text(
                "Live request bodies are intentionally not retained or displayed. "
                "This avoids reflecting credentials or sensitive request metadata."
            )
        else:
            st.json(demo.requests)


def _render_integrations_area() -> None:
    st.header("Tool Integrations")
    _guidance(
        "Choose a goal, then run each integration. For OpenAI and Anthropic, "
        "switch to the hostile proposal to see an invented tool rejected.",
        "Each integration exposes only the allowlisted tools, executes the "
        "proposed calls through ToolRegistry and returns a final message. A "
        "hostile batch is rejected with zero tools executed.",
        "LangChain Agents, OpenAI Function Calling and Anthropic Tool Use run "
        "through the same application-owned authority boundary; provider "
        "output never executes anything by itself. Mem0 is in the Memory area.",
    )
    st.info(
        "Provider access starts in a zero-key state. You may explicitly authorize "
        "your own OpenAI or Anthropic API key for this browser session. PR-01 "
        "stores it only in Streamlit session state and does not make a live call."
    )

    with st.expander("Manage live-provider API keys"):
        st.caption(
            "Enter only credentials you want to authorize for this browser "
            "session. Keys are masked, are not written to a project credential "
            "file, and entering a key alone never triggers a provider request."
        )

        for provider_name, config in PROVIDER_CREDENTIALS.items():
            st.text_input(
                f"{provider_name} API key",
                type="password",
                key=config["session_input_key"],
                placeholder="Enter key",
            )

        st.button(
            "Authorize entered keys for this session",
            on_click=authorize_entered_keys,
            use_container_width=True,
            type="primary",
            key="authorize_session_credentials",
        )

        st.button(
            "Clear all session credentials",
            on_click=clear_authorized_credentials,
            use_container_width=True,
            key="clear_session_credentials",
        )

        notice = st.session_state.get("credential_notice")
        notice_type = st.session_state.get("credential_notice_type")

        if notice:
            if notice_type == "success":
                st.success(notice)
            elif notice_type == "warning":
                st.warning(notice)
            else:
                st.error(notice)

        for provider_name in PROVIDER_CREDENTIALS:
            if authorized_session_key(provider_name):
                st.success(f"{provider_name}: session credential authorized.")
            else:
                st.caption(f"{provider_name}: zero-key state.")

        st.warning(
            "Security reminder: when finished, clear all session credentials "
            "and close this tab, especially on a shared computer. Clearing the "
            "session does not revoke the key at its provider."
        )

    st.warning(EVIDENCE_LIVE)
    preset = st.selectbox(
        "Goal",
        [name for name in GOAL_PRESETS if not name.startswith("No matching")],
        key="integration_preset",
    )
    behaviour = st.radio(
        "Scripted provider proposal (OpenAI / Anthropic)",
        ("Well-behaved", "Hostile: adds an invented 'shell' tool call"),
        key="integration_behaviour",
    )
    goal = GOAL_PRESETS[preset]
    hostile = behaviour != "Well-behaved"

    st.caption(
        "Demo buttons below are deterministic/mock-backed and remain zero-cost. "
        "The separate OpenAI LIVE and Anthropic LIVE buttons perform real provider "
        "requests only when you press them and may consume your provider quota."
    )

    columns = st.columns(3)
    if columns[0].button("Run LangChain agent", key="run_langchain"):
        st.session_state["integration_demo"] = run_langchain_demo(goal)
    if columns[1].button("Run OpenAI function calling", key="run_openai"):
        st.session_state["integration_demo"] = run_openai_demo(goal, hostile=hostile)
    if columns[2].button("Run Anthropic tool use", key="run_anthropic"):
        st.session_state["integration_demo"] = run_anthropic_demo(
            goal, hostile=hostile
        )

    openai_key = authorized_session_key("OpenAI")
    st.markdown("#### OpenAI Live")
    st.caption(
        f"Application-owned model: {OPENAI_LIVE_MODEL}. "
        f"Maximum provider requests: {OPENAI_LIVE_MAX_REQUESTS}; "
        f"maximum tool calls: {OPENAI_LIVE_MAX_TOOL_CALLS}. "
        "Pressing the button below can incur provider cost."
    )
    if st.button(
        "Run OpenAI LIVE - may incur cost",
        key="run_openai_live",
        type="primary",
        disabled=openai_key is None,
    ):
        if openai_key is None:
            st.error("Authorize an OpenAI credential for this session first.")
        else:
            st.session_state["integration_demo"] = run_openai_live(
                goal,
                api_key=openai_key,
            )

    if openai_key is None:
        st.caption(
            "OpenAI LIVE is disabled until an OpenAI credential is explicitly "
            "authorized for this browser session."
        )

    anthropic_live_key = authorized_session_key("Anthropic")
    st.markdown("#### Anthropic Live")
    st.caption(
        f"Application-owned model: {ANTHROPIC_LIVE_MODEL}. "
        f"Maximum provider requests: {ANTHROPIC_LIVE_MAX_REQUESTS}; "
        f"maximum tool calls: {ANTHROPIC_LIVE_MAX_TOOL_CALLS}; "
        f"maximum output tokens/request: {ANTHROPIC_LIVE_MAX_OUTPUT_TOKENS}. "
        "Pressing the button below can incur provider cost."
    )
    if st.button(
        "Run Anthropic LIVE - may incur cost",
        key="run_anthropic_live",
        type="primary",
        disabled=anthropic_live_key is None,
    ):
        st.session_state["integration_demo"] = run_anthropic_live(
            goal,
            api_key=anthropic_live_key or "",
        )
        st.caption(
            "Live request bodies are intentionally not retained or displayed."
        )

    demo: IntegrationDemo | None = st.session_state.get("integration_demo")
    if demo is not None:
        _render_integration_result(demo)


def _render_reliability_area() -> None:
    st.header("Reliability")
    _guidance(
        "Pick a scenario and press Run scenario.",
        "Each scenario is labelled Success, Recovered, Bounded failure or "
        "Denied, with the attempts, paths or lifecycle trace that led there.",
        "Retries are bounded and only for retryable faults, deadlines cancel "
        "slow work, fallback is explicit and visible, the step budget stops a "
        "runaway agent, and unsafe proposals are denied before execution "
        "(M5-L04).",
    )
    st.caption(
        f"{EVIDENCE_DETERMINISTIC}. Faults are injected locally; no remote "
        "provider is involved."
    )
    scenario = st.selectbox(
        "Scenario", list(RELIABILITY_SCENARIOS), key="reliability_scenario"
    )
    if st.button("Run scenario", key="run_reliability"):
        st.session_state["reliability_outcome"] = run_reliability_scenario(scenario)

    outcome: ReliabilityOutcome | None = st.session_state.get("reliability_outcome")
    if outcome is None:
        return
    message = f"{outcome.scenario}: {outcome.classification}"
    if outcome.classification in (SUCCESS, RECOVERED):
        st.success(message)
    elif outcome.classification == BOUNDED_FAILURE:
        st.warning(message)
    else:
        st.error(message)
    st.text(outcome.summary)
    st.dataframe(
        [{key: str(value) for key, value in event.items()} for event in outcome.events],
        hide_index=True,
    )


def main() -> None:
    """Render the Module 5 demonstration page."""
    st.set_page_config(page_title="Module 5: AI Agent Engineering", layout="wide")
    _render_header()
    tabs = st.tabs(list(AREAS))
    with tabs[0]:
        _render_agent_area()
    with tabs[1]:
        _render_memory_area()
    with tabs[2]:
        _render_integrations_area()
    with tabs[3]:
        _render_reliability_area()


if __name__ == "__main__":
    main()

st.caption(
    "Developed from Techademy AI Engineering program requirements. "
    "Independent implementation, engineering enhancements, and deployment."
)
