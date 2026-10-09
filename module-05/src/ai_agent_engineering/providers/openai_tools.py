"""OpenAI function-calling integration for Module 5.

OpenAI-generated tool calls are treated as untrusted provider data. Tool
authority, argument validation, authorization, and execution remain owned by
the Module 5 ToolRegistry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ai_agent_engineering.tools.registry import ToolRegistry
from ai_agent_engineering.tools.schemas import ToolDefinition

MAX_OPENAI_REQUESTS = 10
MAX_OPENAI_TOOL_CALLS = 20


class OpenAIToolCallError(ValueError):
    """Raised when an OpenAI tool call cannot be normalized safely."""


class OpenAIToolLoopBudgetError(RuntimeError):
    """Raised when an OpenAI request loop exceeds its application budget."""


@dataclass(frozen=True, slots=True)
class OpenAIToolCall:
    """Normalized OpenAI function call proposed to the application.

    Attributes:
        call_id: Provider-generated identifier used to correlate tool output.
        name: Untrusted proposed tool name.
        arguments: Untrusted proposed arguments parsed from provider JSON.
    """

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class OpenAIFunctionCallingResult:
    """Terminal result of a bounded OpenAI function-calling request loop.

    Attributes:
        output_text: Final untrusted provider text returned without tool calls.
        executed_calls: Calls the application validated and executed in order.
        request_count: Number of provider requests sent.
    """

    output_text: str
    executed_calls: tuple[OpenAIToolCall, ...]
    request_count: int


def to_openai_response_tool(
    definition: ToolDefinition,
) -> dict[str, Any]:
    """Convert an application tool definition to an OpenAI Responses tool.

    Args:
        definition: Application-owned allowlisted tool definition.

    Returns:
        OpenAI Responses API function-tool schema.
    """
    return {
        "type": "function",
        "name": definition.name,
        "description": definition.description,
        "parameters": dict(definition.input_schema),
        "strict": True,
    }


def to_openai_chat_tool(
    definition: ToolDefinition,
) -> dict[str, Any]:
    """Convert an application tool definition to a Chat Completions tool.

    Args:
        definition: Application-owned allowlisted tool definition.

    Returns:
        OpenAI Chat Completions function-tool schema.
    """
    return {
        "type": "function",
        "function": {
            "name": definition.name,
            "description": definition.description,
            "parameters": dict(definition.input_schema),
            "strict": True,
        },
    }


def response_tools(
    registry: ToolRegistry,
) -> tuple[dict[str, Any], ...]:
    """Expose only application-allowlisted tools in Responses API format.

    Args:
        registry: Application-owned tool registry.

    Returns:
        Stable tuple of OpenAI Responses API tool definitions.
    """
    return tuple(
        to_openai_response_tool(definition)
        for definition in registry.definitions()
    )


def chat_tools(
    registry: ToolRegistry,
) -> tuple[dict[str, Any], ...]:
    """Expose only application-allowlisted tools in Chat API format.

    Args:
        registry: Application-owned tool registry.

    Returns:
        Stable tuple of OpenAI Chat Completions tool definitions.
    """
    return tuple(
        to_openai_chat_tool(definition)
        for definition in registry.definitions()
    )


def _parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    """Parse untrusted OpenAI JSON arguments into a mapping.

    Args:
        raw_arguments: Provider-supplied JSON string.

    Returns:
        Parsed object arguments.

    Raises:
        OpenAIToolCallError: If arguments are not valid JSON objects.
    """
    if not isinstance(raw_arguments, str):
        raise OpenAIToolCallError(
            "OpenAI function arguments must be a JSON string."
        )

    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise OpenAIToolCallError(
            "OpenAI function arguments are not valid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise OpenAIToolCallError(
            "OpenAI function arguments must decode to an object."
        )

    return parsed


def normalize_response_tool_call(call: Any) -> OpenAIToolCall:
    """Normalize an OpenAI Responses API function-call item.

    Args:
        call: Provider response item with call_id, name, and arguments.

    Returns:
        Provider-neutral normalized function call.

    Raises:
        OpenAIToolCallError: If required provider fields are malformed.
    """
    call_id = getattr(call, "call_id", None)
    name = getattr(call, "name", None)
    raw_arguments = getattr(call, "arguments", None)

    if not isinstance(call_id, str) or not call_id.strip():
        raise OpenAIToolCallError(
            "OpenAI response tool call requires a non-empty call_id."
        )

    if not isinstance(name, str) or not name.strip():
        raise OpenAIToolCallError(
            "OpenAI response tool call requires a non-empty function name."
        )

    return OpenAIToolCall(
        call_id=call_id,
        name=name,
        arguments=_parse_arguments(raw_arguments),
    )


def normalize_chat_tool_call(call: Any) -> OpenAIToolCall:
    """Normalize an OpenAI Chat Completions function-tool call.

    Args:
        call: Provider tool-call object containing a function payload.

    Returns:
        Provider-neutral normalized function call.

    Raises:
        OpenAIToolCallError: If required provider fields are malformed.
    """
    call_id = getattr(call, "id", None)
    function = getattr(call, "function", None)

    if not isinstance(call_id, str) or not call_id.strip():
        raise OpenAIToolCallError(
            "OpenAI chat tool call requires a non-empty id."
        )

    if function is None:
        raise OpenAIToolCallError(
            "OpenAI chat tool call requires a function payload."
        )

    name = getattr(function, "name", None)
    raw_arguments = getattr(function, "arguments", None)

    if not isinstance(name, str) or not name.strip():
        raise OpenAIToolCallError(
            "OpenAI chat tool call requires a non-empty function name."
        )

    return OpenAIToolCall(
        call_id=call_id,
        name=name,
        arguments=_parse_arguments(raw_arguments),
    )


def execute_openai_tool_call(
    registry: ToolRegistry,
    call: OpenAIToolCall,
) -> Any:
    """Execute a normalized call through application-owned authority.

    OpenAI does not receive execution authority. The proposed tool name and
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


def run_openai_function_calling(
    client: Any,
    registry: ToolRegistry,
    *,
    model: str,
    user_input: str,
    max_requests: int = 4,
    max_tool_calls: int = 8,
) -> OpenAIFunctionCallingResult:
    """Run a bounded OpenAI Responses API function-calling loop.

    The application sends only registry-derived tool schemas. Each provider
    response is untrusted: every proposed call in a response is normalized and
    validated by the registry before any of them executes, then executed only
    through ``ToolRegistry``. Tool results are returned to OpenAI as
    ``function_call_output`` items continuing the previous response. The loop
    ends when the provider returns no function calls, or fails closed when an
    application-owned budget is exhausted.

    The client is always supplied by the caller. This function never creates a
    client or reads credentials, so tests can inject a mocked transport and live
    use remains an explicit caller decision.

    Args:
        client: OpenAI SDK client exposing ``responses.create``.
        registry: Application-owned allowlisted tool registry.
        model: OpenAI model identifier selected by the application.
        user_input: User goal sent as the initial request input.
        max_requests: Maximum number of provider requests.
        max_tool_calls: Maximum number of tool executions across the loop.

    Returns:
        Final provider text, executed calls, and request count.

    Raises:
        ValueError: If model, input, or budgets are invalid.
        OpenAIToolCallError: If a provider response or call is malformed.
        OpenAIToolLoopBudgetError: If a budget is exhausted.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError("OpenAI model must be a non-empty string.")

    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("OpenAI user input must be a non-empty string.")

    max_requests = _bounded_budget(
        max_requests, MAX_OPENAI_REQUESTS, "max_requests"
    )
    max_tool_calls = _bounded_budget(
        max_tool_calls, MAX_OPENAI_TOOL_CALLS, "max_tool_calls"
    )

    tools = list(response_tools(registry))
    executed: list[OpenAIToolCall] = []
    request_input: Any = user_input
    previous_response_id: str | None = None

    for request_count in range(1, max_requests + 1):
        request: dict[str, Any] = {
            "model": model,
            "input": request_input,
            "tools": tools,
        }
        if previous_response_id is not None:
            request["previous_response_id"] = previous_response_id

        response = client.responses.create(**request)

        response_id = getattr(response, "id", None)
        output = getattr(response, "output", None)

        if not isinstance(response_id, str) or not response_id.strip():
            raise OpenAIToolCallError(
                "OpenAI response requires a non-empty id."
            )

        if not isinstance(output, list):
            raise OpenAIToolCallError(
                "OpenAI response output must be a list."
            )

        calls = [
            normalize_response_tool_call(item)
            for item in output
            if getattr(item, "type", None) == "function_call"
        ]

        if not calls:
            output_text = getattr(response, "output_text", "")
            if not isinstance(output_text, str):
                raise OpenAIToolCallError(
                    "OpenAI response output_text must be a string."
                )

            return OpenAIFunctionCallingResult(
                output_text=output_text,
                executed_calls=tuple(executed),
                request_count=request_count,
            )

        if len(executed) + len(calls) > max_tool_calls:
            raise OpenAIToolLoopBudgetError(
                "OpenAI tool-call budget exhausted."
            )

        for call in calls:
            registry.validate_call(call.name, call.arguments)

        outputs: list[dict[str, str]] = []

        for call in calls:
            result = execute_openai_tool_call(registry, call)
            executed.append(call)
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result),
                }
            )

        request_input = outputs
        previous_response_id = response_id

    raise OpenAIToolLoopBudgetError("OpenAI request budget exhausted.")
