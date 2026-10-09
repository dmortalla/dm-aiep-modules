"""Tests for the OpenAI function-calling provider boundary."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from ai_agent_engineering.providers.openai_tools import (
    MAX_OPENAI_REQUESTS,
    MAX_OPENAI_TOOL_CALLS,
    OpenAIFunctionCallingResult,
    OpenAIToolCall,
    OpenAIToolCallError,
    OpenAIToolLoopBudgetError,
    chat_tools,
    execute_openai_tool_call,
    normalize_chat_tool_call,
    normalize_response_tool_call,
    response_tools,
    run_openai_function_calling,
)
from ai_agent_engineering.tools import (
    ToolRegistry,
    ToolValidationError,
    UnknownToolError,
    build_default_registry,
)
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.responses.response_function_tool_call import (
    ResponseFunctionToolCall,
)


def test_response_tools_expose_only_registry_allowlist() -> None:
    registry = build_default_registry()

    tools = response_tools(registry)

    assert tuple(tool["name"] for tool in tools) == registry.names()
    assert all(tool["type"] == "function" for tool in tools)
    assert all(tool["strict"] is True for tool in tools)


def test_chat_tools_expose_only_registry_allowlist() -> None:
    registry = build_default_registry()

    tools = chat_tools(registry)

    assert tuple(
        tool["function"]["name"]
        for tool in tools
    ) == registry.names()

    assert all(tool["type"] == "function" for tool in tools)
    assert all(
        tool["function"]["strict"] is True
        for tool in tools
    )


def test_response_tool_schema_preserves_calculator_contract() -> None:
    registry = build_default_registry()

    calculator = next(
        tool
        for tool in response_tools(registry)
        if tool["name"] == "calculator"
    )

    parameters = calculator["parameters"]

    assert parameters["required"] == [
        "operation",
        "left",
        "right",
    ]
    assert parameters["additionalProperties"] is False


def test_normalize_real_openai_response_function_call() -> None:
    call = ResponseFunctionToolCall(
        id="response-item",
        call_id="call-42",
        type="function_call",
        name="calculator",
        arguments=(
            '{"operation":"multiply","left":6,"right":7}'
        ),
        status="completed",
    )

    normalized = normalize_response_tool_call(call)

    assert normalized == OpenAIToolCall(
        call_id="call-42",
        name="calculator",
        arguments={
            "operation": "multiply",
            "left": 6,
            "right": 7,
        },
    )


def test_normalize_real_openai_chat_function_call() -> None:
    call = ChatCompletionMessageFunctionToolCall(
        id="call-42",
        type="function",
        function={
            "name": "calculator",
            "arguments": (
                '{"operation":"multiply","left":6,"right":7}'
            ),
        },
    )

    normalized = normalize_chat_tool_call(call)

    assert normalized == OpenAIToolCall(
        call_id="call-42",
        name="calculator",
        arguments={
            "operation": "multiply",
            "left": 6,
            "right": 7,
        },
    )


def test_normalized_openai_call_executes_through_registry() -> None:
    registry = build_default_registry()

    call = OpenAIToolCall(
        call_id="call-42",
        name="calculator",
        arguments={
            "operation": "multiply",
            "left": 6,
            "right": 7,
        },
    )

    result = execute_openai_tool_call(
        registry,
        call,
    )

    assert result == {
        "operation": "multiply",
        "result": 42.0,
    }


def test_openai_cannot_invent_tool_authority() -> None:
    registry = build_default_registry()

    call = OpenAIToolCall(
        call_id="hostile-call",
        name="shell",
        arguments={
            "command": "whoami",
        },
    )

    with pytest.raises(UnknownToolError):
        execute_openai_tool_call(
            registry,
            call,
        )

    assert "shell" not in registry.names()


def test_openai_cannot_inject_extra_arguments() -> None:
    registry = build_default_registry()

    call = OpenAIToolCall(
        call_id="hostile-call",
        name="calculator",
        arguments={
            "operation": "multiply",
            "left": 6,
            "right": 7,
            "command": "whoami",
        },
    )

    with pytest.raises(ToolValidationError):
        execute_openai_tool_call(
            registry,
            call,
        )


@pytest.mark.parametrize(
    "raw_arguments",
    (
        "not-json",
        "[]",
        '"text"',
        "42",
        "null",
    ),
)
def test_malformed_openai_arguments_fail_closed(
    raw_arguments: str,
) -> None:
    call = SimpleNamespace(
        call_id="bad-call",
        name="calculator",
        arguments=raw_arguments,
    )

    with pytest.raises(OpenAIToolCallError):
        normalize_response_tool_call(call)


@pytest.mark.parametrize(
    ("call_id", "name"),
    (
        ("", "calculator"),
        ("call-1", ""),
        (None, "calculator"),
        ("call-1", None),
    ),
)
def test_malformed_response_call_metadata_fails_closed(
    call_id: object,
    name: object,
) -> None:
    call = SimpleNamespace(
        call_id=call_id,
        name=name,
        arguments="{}",
    )

    with pytest.raises(OpenAIToolCallError):
        normalize_response_tool_call(call)


def test_chat_call_without_function_payload_fails_closed() -> None:
    call = SimpleNamespace(
        id="call-1",
        function=None,
    )

    with pytest.raises(OpenAIToolCallError):
        normalize_chat_tool_call(call)


# Request-loop tests use a real OpenAI SDK client whose HTTP transport is an
# httpx.MockTransport. Requests are serialized and responses parsed by the
# genuine SDK, but nothing leaves the process: this is mocked-transport
# evidence, not live OpenAI evidence.

MOCK_BASE_URL = "https://openai-mock.invalid/v1"

CALCULATOR_ARGUMENTS = '{"operation":"multiply","left":6,"right":7}'


def _function_call_item(
    call_id: str,
    name: str,
    arguments: str,
) -> dict[str, object]:
    return {
        "type": "function_call",
        "id": f"fc-{call_id}",
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
    }


def _message_item(text: str) -> dict[str, object]:
    return {
        "type": "message",
        "id": "msg-final",
        "role": "assistant",
        "status": "completed",
        "content": [
            {
                "type": "output_text",
                "text": text,
                "annotations": [],
            }
        ],
    }


def _response_payload(
    response_id: str,
    output: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": 0,
        "model": "mock-model",
        "status": "completed",
        "output": output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
    }


class _ScriptedOpenAI:
    """Real OpenAI client backed by scripted mocked HTTP responses."""

    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.requests: list[dict[str, object]] = []
        self._payloads = list(payloads)

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert str(request.url) == f"{MOCK_BASE_URL}/responses"
            self.requests.append(json.loads(request.content))
            if not self._payloads:
                raise AssertionError("Unexpected extra OpenAI request.")
            return httpx.Response(200, json=self._payloads.pop(0))

        self.client = OpenAI(
            api_key="mock-key-not-a-credential",
            base_url=MOCK_BASE_URL,
            max_retries=0,
            http_client=httpx.Client(
                transport=httpx.MockTransport(handler),
            ),
        )


def _spy_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ToolRegistry, list[str]]:
    registry = build_default_registry()
    executed: list[str] = []
    original = registry.execute

    def spy(name: str, arguments: dict[str, object]) -> object:
        executed.append(name)
        return original(name, arguments)

    monkeypatch.setattr(registry, "execute", spy)
    return registry, executed


def test_request_loop_sends_tools_executes_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedOpenAI(
        [
            _response_payload(
                "resp-1",
                [
                    _function_call_item(
                        "call-1", "calculator", CALCULATOR_ARGUMENTS
                    )
                ],
            ),
            _response_payload("resp-2", [_message_item("6 x 7 = 42")]),
        ]
    )

    result = run_openai_function_calling(
        provider.client,
        registry,
        model="mock-model",
        user_input="What is 6 times 7?",
    )

    first, second = provider.requests

    assert first == {
        "model": "mock-model",
        "input": "What is 6 times 7?",
        "tools": list(response_tools(registry)),
    }
    assert "previous_response_id" not in first

    assert second["previous_response_id"] == "resp-1"
    assert second["tools"] == list(response_tools(registry))
    assert second["input"] == [
        {
            "type": "function_call_output",
            "call_id": "call-1",
            "output": json.dumps({"operation": "multiply", "result": 42.0}),
        }
    ]

    assert executed == ["calculator"]
    assert result == OpenAIFunctionCallingResult(
        output_text="6 x 7 = 42",
        executed_calls=(
            OpenAIToolCall(
                call_id="call-1",
                name="calculator",
                arguments={"operation": "multiply", "left": 6, "right": 7},
            ),
        ),
        request_count=2,
    )


def test_request_loop_supports_multi_step_tool_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedOpenAI(
        [
            _response_payload(
                "resp-1",
                [
                    _function_call_item(
                        "call-1", "calculator", CALCULATOR_ARGUMENTS
                    )
                ],
            ),
            _response_payload(
                "resp-2",
                [
                    _function_call_item(
                        "call-2",
                        "calculator",
                        '{"operation":"add","left":42,"right":8}',
                    )
                ],
            ),
            _response_payload("resp-3", [_message_item("50")]),
        ]
    )

    result = run_openai_function_calling(
        provider.client,
        registry,
        model="mock-model",
        user_input="Multiply 6 by 7, then add 8.",
    )

    assert executed == ["calculator", "calculator"]
    assert [
        request.get("previous_response_id")
        for request in provider.requests
    ] == [None, "resp-1", "resp-2"]
    assert result.output_text == "50"
    assert result.request_count == 3
    assert [call.call_id for call in result.executed_calls] == [
        "call-1",
        "call-2",
    ]


def test_request_loop_denies_invented_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedOpenAI(
        [
            _response_payload(
                "resp-1",
                [_function_call_item("call-1", "shell", '{"command":"whoami"}')],
            )
        ]
    )

    with pytest.raises(UnknownToolError):
        run_openai_function_calling(
            provider.client,
            registry,
            model="mock-model",
            user_input="Run whoami.",
        )

    assert executed == []
    assert len(provider.requests) == 1
    assert "shell" not in registry.names()


def test_request_loop_denies_injected_arguments_before_any_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedOpenAI(
        [
            _response_payload(
                "resp-1",
                [
                    _function_call_item(
                        "call-1", "calculator", CALCULATOR_ARGUMENTS
                    ),
                    _function_call_item(
                        "call-2",
                        "calculator",
                        '{"operation":"multiply","left":6,"right":7,'
                        '"command":"whoami"}',
                    ),
                ],
            )
        ]
    )

    with pytest.raises(ToolValidationError):
        run_openai_function_calling(
            provider.client,
            registry,
            model="mock-model",
            user_input="Multiply.",
        )

    assert executed == []
    assert len(provider.requests) == 1


def test_request_loop_denies_malformed_provider_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedOpenAI(
        [
            _response_payload(
                "resp-1",
                [_function_call_item("call-1", "calculator", "not-json")],
            )
        ]
    )

    with pytest.raises(OpenAIToolCallError):
        run_openai_function_calling(
            provider.client,
            registry,
            model="mock-model",
            user_input="Multiply.",
        )

    assert executed == []


def test_request_loop_rejects_response_without_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    payload = _response_payload(
        "resp-1",
        [_function_call_item("call-1", "calculator", CALCULATOR_ARGUMENTS)],
    )
    del payload["id"]
    provider = _ScriptedOpenAI([payload])

    with pytest.raises(OpenAIToolCallError):
        run_openai_function_calling(
            provider.client,
            registry,
            model="mock-model",
            user_input="Multiply.",
        )

    assert executed == []


def test_request_budget_terminates_endless_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedOpenAI(
        [
            _response_payload(
                f"resp-{index}",
                [
                    _function_call_item(
                        f"call-{index}", "calculator", CALCULATOR_ARGUMENTS
                    )
                ],
            )
            for index in range(5)
        ]
    )

    with pytest.raises(OpenAIToolLoopBudgetError):
        run_openai_function_calling(
            provider.client,
            registry,
            model="mock-model",
            user_input="Keep calculating.",
            max_requests=3,
        )

    assert len(provider.requests) == 3
    assert executed == ["calculator"] * 3


def test_tool_call_budget_denies_oversized_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedOpenAI(
        [
            _response_payload(
                "resp-1",
                [
                    _function_call_item(
                        f"call-{index}", "calculator", CALCULATOR_ARGUMENTS
                    )
                    for index in range(3)
                ],
            )
        ]
    )

    with pytest.raises(OpenAIToolLoopBudgetError):
        run_openai_function_calling(
            provider.client,
            registry,
            model="mock-model",
            user_input="Calculate three times.",
            max_tool_calls=2,
        )

    assert executed == []


@pytest.mark.parametrize(
    ("max_requests", "max_tool_calls"),
    (
        (0, 8),
        (MAX_OPENAI_REQUESTS + 1, 8),
        (True, 8),
        (4, 0),
        (4, MAX_OPENAI_TOOL_CALLS + 1),
    ),
)
def test_request_loop_rejects_invalid_budgets(
    max_requests: int,
    max_tool_calls: int,
) -> None:
    provider = _ScriptedOpenAI([])

    with pytest.raises(ValueError):
        run_openai_function_calling(
            provider.client,
            build_default_registry(),
            model="mock-model",
            user_input="Multiply.",
            max_requests=max_requests,
            max_tool_calls=max_tool_calls,
        )

    assert provider.requests == []
