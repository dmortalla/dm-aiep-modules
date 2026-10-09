"""Anthropic tool-use integration for Module 5.

Anthropic-generated tool-use blocks are treated as untrusted provider data.
Tool authority, argument validation, authorization, and execution remain owned
by the Module 5 ToolRegistry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ai_agent_engineering.tools.registry import ToolRegistry
from ai_agent_engineering.tools.schemas import ToolDefinition

MAX_ANTHROPIC_REQUESTS = 10
MAX_ANTHROPIC_TOOL_CALLS = 20
MAX_ANTHROPIC_OUTPUT_TOKENS = 4096

_TERMINAL_STOP_REASONS = frozenset({"end_turn", "stop_sequence"})


class AnthropicToolUseError(ValueError):
    """Raised when an Anthropic tool-use response cannot be handled safely."""


class AnthropicToolLoopBudgetError(RuntimeError):
    """Raised when an Anthropic request loop exceeds its application budget."""


@dataclass(frozen=True, slots=True)
class AnthropicToolUse:
    """Normalized Anthropic tool-use request proposed to the application.

    Attributes:
        tool_use_id: Provider-generated identifier used to correlate results.
        name: Untrusted proposed tool name.
        arguments: Untrusted proposed arguments from the tool-use input.
    """

    tool_use_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AnthropicToolUseResult:
    """Terminal result of a bounded Anthropic tool-use request loop.

    Attributes:
        output_text: Final untrusted provider text from the terminal message.
        stop_reason: Terminal provider stop reason.
        executed_calls: Calls the application validated and executed in order.
        request_count: Number of provider requests sent.
    """

    output_text: str
    stop_reason: str
    executed_calls: tuple[AnthropicToolUse, ...]
    request_count: int


def to_anthropic_tool(definition: ToolDefinition) -> dict[str, Any]:
    """Convert an application tool definition to an Anthropic custom tool.

    Args:
        definition: Application-owned allowlisted tool definition.

    Returns:
        Anthropic Messages API custom-tool definition.
    """
    return {
        "name": definition.name,
        "description": definition.description,
        "input_schema": dict(definition.input_schema),
    }


def anthropic_tools(
    registry: ToolRegistry,
) -> tuple[dict[str, Any], ...]:
    """Expose only application-allowlisted tools in Anthropic format.

    Args:
        registry: Application-owned tool registry.

    Returns:
        Stable tuple of Anthropic Messages API tool definitions.
    """
    return tuple(
        to_anthropic_tool(definition)
        for definition in registry.definitions()
    )


def normalize_tool_use_block(block: Any) -> AnthropicToolUse:
    """Normalize an Anthropic ``tool_use`` content block.

    Args:
        block: Provider content block with id, name, input, and caller.

    Returns:
        Normalized tool-use proposal.

    Raises:
        AnthropicToolUseError: If required provider fields are malformed or
            the call was not made directly by the model.
    """
    tool_use_id = getattr(block, "id", None)
    name = getattr(block, "name", None)
    arguments = getattr(block, "input", None)
    caller = getattr(block, "caller", None)

    if not isinstance(tool_use_id, str) or not tool_use_id.strip():
        raise AnthropicToolUseError(
            "Anthropic tool_use block requires a non-empty id."
        )

    if not isinstance(name, str) or not name.strip():
        raise AnthropicToolUseError(
            "Anthropic tool_use block requires a non-empty tool name."
        )

    if not isinstance(arguments, dict):
        raise AnthropicToolUseError(
            "Anthropic tool_use input must be an object."
        )

    # Module 5 enables no server-side tools, so only direct model calls are
    # acceptable. Calls attributed to a provider-side caller are denied.
    if caller is not None and getattr(caller, "type", None) != "direct":
        raise AnthropicToolUseError(
            "Anthropic tool_use block must come from a direct caller."
        )

    return AnthropicToolUse(
        tool_use_id=tool_use_id,
        name=name,
        arguments=dict(arguments),
    )


def execute_anthropic_tool_use(
    registry: ToolRegistry,
    call: AnthropicToolUse,
) -> Any:
    """Execute a normalized call through application-owned authority.

    Anthropic does not receive execution authority. The proposed tool name and
    arguments must pass the Module 5 registry's allowlist, authorization, and
    JSON-schema validation before the handler can run.

    Args:
        registry: Application-owned allowlisted tool registry.
        call: Untrusted normalized provider proposal.

    Returns:
        Result produced by the validated application tool.
    """
    return registry.execute(
        call.name,
        call.arguments,
    )


def _bounded_budget(value: int, limit: int, label: str) -> int:
    """Validate an application-owned loop budget.

    Raises:
        ValueError: If the budget is not an integer within ``1..limit``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")

    if not 1 <= value <= limit:
        raise ValueError(f"{label} must be between 1 and {limit}.")

    return value


def _read_content(
    content: Any,
) -> tuple[list[str], list[AnthropicToolUse]]:
    """Split untrusted response content into text and tool-use proposals.

    Raises:
        AnthropicToolUseError: If content is malformed, contains a block type
            Module 5 did not enable, or repeats a tool_use id.
    """
    if not isinstance(content, list):
        raise AnthropicToolUseError(
            "Anthropic message content must be a list."
        )

    texts: list[str] = []
    calls: list[AnthropicToolUse] = []

    for block in content:
        block_type = getattr(block, "type", None)

        if block_type == "text":
            text = getattr(block, "text", None)
            if not isinstance(text, str):
                raise AnthropicToolUseError(
                    "Anthropic text block requires string text."
                )
            texts.append(text)
        elif block_type == "tool_use":
            calls.append(normalize_tool_use_block(block))
        else:
            raise AnthropicToolUseError(
                f"Unsupported Anthropic content block type: {block_type!r}"
            )

    ids = [call.tool_use_id for call in calls]
    if len(ids) != len(set(ids)):
        raise AnthropicToolUseError(
            "Anthropic tool_use ids must be unique within a message."
        )

    return texts, calls


def run_anthropic_tool_use(
    client: Any,
    registry: ToolRegistry,
    *,
    model: str,
    user_input: str,
    max_tokens: int = 1024,
    max_requests: int = 4,
    max_tool_calls: int = 8,
) -> AnthropicToolUseResult:
    """Run a bounded Anthropic Messages API tool-use loop.

    The application sends only registry-derived tool schemas. Each provider
    message is untrusted: every ``tool_use`` block in a message is normalized
    and validated by the registry before any of them executes, then executed
    only through ``ToolRegistry``. The Messages API is stateless, so the
    application resends the conversation: the assistant turn is rebuilt from
    the normalized text and tool-use data, followed by a user turn of
    ``tool_result`` blocks. The loop ends on a terminal stop reason, or fails
    closed on any other stop reason or when an application-owned budget is
    exhausted.

    The client is always supplied by the caller. This function never creates a
    client or reads credentials, so tests can inject a mocked transport and live
    use remains an explicit caller decision.

    Args:
        client: Anthropic SDK client exposing ``messages.create``.
        registry: Application-owned allowlisted tool registry.
        model: Anthropic model identifier selected by the application.
        user_input: User goal sent as the initial user message.
        max_tokens: Maximum output tokens per provider request.
        max_requests: Maximum number of provider requests.
        max_tool_calls: Maximum number of tool executions across the loop.

    Returns:
        Final provider text, stop reason, executed calls, and request count.

    Raises:
        ValueError: If model, input, or budgets are invalid.
        AnthropicToolUseError: If a provider message or block is malformed.
        AnthropicToolLoopBudgetError: If a budget is exhausted.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Anthropic model must be a non-empty string.")

    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("Anthropic user input must be a non-empty string.")

    max_tokens = _bounded_budget(
        max_tokens, MAX_ANTHROPIC_OUTPUT_TOKENS, "max_tokens"
    )
    max_requests = _bounded_budget(
        max_requests, MAX_ANTHROPIC_REQUESTS, "max_requests"
    )
    max_tool_calls = _bounded_budget(
        max_tool_calls, MAX_ANTHROPIC_TOOL_CALLS, "max_tool_calls"
    )

    tools = list(anthropic_tools(registry))
    executed: list[AnthropicToolUse] = []
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_input},
    ]

    for request_count in range(1, max_requests + 1):
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=list(messages),
            tools=tools,
        )

        stop_reason = getattr(message, "stop_reason", None)
        texts, calls = _read_content(getattr(message, "content", None))

        if stop_reason in _TERMINAL_STOP_REASONS:
            if calls:
                raise AnthropicToolUseError(
                    "Anthropic terminal message must not request tools."
                )

            return AnthropicToolUseResult(
                output_text="".join(texts),
                stop_reason=stop_reason,
                executed_calls=tuple(executed),
                request_count=request_count,
            )

        if stop_reason != "tool_use":
            raise AnthropicToolUseError(
                f"Unsupported Anthropic stop reason: {stop_reason!r}"
            )

        if not calls:
            raise AnthropicToolUseError(
                "Anthropic tool_use stop reason requires tool_use blocks."
            )

        if len(executed) + len(calls) > max_tool_calls:
            raise AnthropicToolLoopBudgetError(
                "Anthropic tool-call budget exhausted."
            )

        for call in calls:
            registry.validate_call(call.name, call.arguments)

        results: list[dict[str, Any]] = []

        for call in calls:
            result = execute_anthropic_tool_use(registry, call)
            executed.append(call)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.tool_use_id,
                    "content": json.dumps(result),
                }
            )

        assistant_content: list[dict[str, Any]] = [
            {"type": "text", "text": text} for text in texts if text
        ]
        assistant_content.extend(
            {
                "type": "tool_use",
                "id": call.tool_use_id,
                "name": call.name,
                "input": call.arguments,
            }
            for call in calls
        )

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": results})

    raise AnthropicToolLoopBudgetError("Anthropic request budget exhausted.")
