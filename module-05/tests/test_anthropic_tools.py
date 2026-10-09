"""Tests for the Anthropic tool-use provider boundary."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx2
import pytest
from ai_agent_engineering.providers.anthropic_tools import (
    MAX_ANTHROPIC_OUTPUT_TOKENS,
    MAX_ANTHROPIC_REQUESTS,
    MAX_ANTHROPIC_TOOL_CALLS,
    AnthropicToolLoopBudgetError,
    AnthropicToolUse,
    AnthropicToolUseError,
    AnthropicToolUseResult,
    anthropic_tools,
    execute_anthropic_tool_use,
    normalize_tool_use_block,
    run_anthropic_tool_use,
)
from ai_agent_engineering.tools import (
    ToolRegistry,
    ToolValidationError,
    UnknownToolError,
    build_default_registry,
)
from anthropic import Anthropic
from anthropic.types import ToolParam, ToolUseBlock
from pydantic import TypeAdapter

CALCULATOR_INPUT = {"operation": "multiply", "left": 6, "right": 7}


def test_anthropic_tools_expose_only_registry_allowlist() -> None:
    registry = build_default_registry()

    tools = anthropic_tools(registry)

    assert tuple(tool["name"] for tool in tools) == registry.names()
    assert all(
        set(tool) == {"name", "description", "input_schema"}
        for tool in tools
    )


def test_anthropic_tools_satisfy_installed_sdk_tool_param() -> None:
    adapter = TypeAdapter(ToolParam)

    for tool in anthropic_tools(build_default_registry()):
        assert adapter.validate_python(tool) == tool


def test_anthropic_tool_schema_preserves_calculator_contract() -> None:
    calculator = next(
        tool
        for tool in anthropic_tools(build_default_registry())
        if tool["name"] == "calculator"
    )

    schema = calculator["input_schema"]

    assert schema["type"] == "object"
    assert schema["required"] == ["operation", "left", "right"]
    assert schema["additionalProperties"] is False


def test_normalize_real_anthropic_tool_use_block() -> None:
    block = ToolUseBlock(
        id="toolu_42",
        type="tool_use",
        name="calculator",
        input=CALCULATOR_INPUT,
        caller={"type": "direct"},
    )

    assert normalize_tool_use_block(block) == AnthropicToolUse(
        tool_use_id="toolu_42",
        name="calculator",
        arguments=CALCULATOR_INPUT,
    )


def test_normalized_anthropic_call_executes_through_registry() -> None:
    call = AnthropicToolUse(
        tool_use_id="toolu_42",
        name="calculator",
        arguments=CALCULATOR_INPUT,
    )

    assert execute_anthropic_tool_use(build_default_registry(), call) == {
        "operation": "multiply",
        "result": 42.0,
    }


def test_anthropic_cannot_invent_tool_authority() -> None:
    registry = build_default_registry()
    call = AnthropicToolUse(
        tool_use_id="toolu_hostile",
        name="shell",
        arguments={"command": "whoami"},
    )

    with pytest.raises(UnknownToolError):
        execute_anthropic_tool_use(registry, call)

    assert "shell" not in registry.names()


def test_anthropic_cannot_inject_extra_arguments() -> None:
    call = AnthropicToolUse(
        tool_use_id="toolu_hostile",
        name="calculator",
        arguments={**CALCULATOR_INPUT, "command": "whoami"},
    )

    with pytest.raises(ToolValidationError):
        execute_anthropic_tool_use(build_default_registry(), call)


@pytest.mark.parametrize(
    ("tool_use_id", "name", "tool_input"),
    (
        ("", "calculator", {}),
        ("toolu_1", "", {}),
        (None, "calculator", {}),
        ("toolu_1", None, {}),
        ("toolu_1", "calculator", "not-an-object"),
        ("toolu_1", "calculator", ["list"]),
        ("toolu_1", "calculator", None),
    ),
)
def test_malformed_tool_use_block_fails_closed(
    tool_use_id: object,
    name: object,
    tool_input: object,
) -> None:
    block = SimpleNamespace(
        id=tool_use_id,
        name=name,
        input=tool_input,
        caller=None,
    )

    with pytest.raises(AnthropicToolUseError):
        normalize_tool_use_block(block)


def test_tool_use_from_non_direct_caller_fails_closed() -> None:
    block = SimpleNamespace(
        id="toolu_1",
        name="calculator",
        input=CALCULATOR_INPUT,
        caller=SimpleNamespace(type="code_execution_20250825"),
    )

    with pytest.raises(AnthropicToolUseError):
        normalize_tool_use_block(block)


# Request-loop tests use a real Anthropic SDK client whose HTTP transport is an
# httpx2.MockTransport. Requests are serialized and responses parsed by the
# genuine SDK, but nothing leaves the process: this is mocked-transport
# evidence, not live Anthropic evidence.

MOCK_BASE_URL = "https://anthropic-mock.invalid"


def _tool_use_block(
    tool_use_id: str,
    name: str,
    tool_input: object,
) -> dict[str, object]:
    return {
        "type": "tool_use",
        "id": tool_use_id,
        "name": name,
        "input": tool_input,
    }


def _text_block(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


def _message_payload(
    message_id: str,
    content: list[dict[str, object]],
    stop_reason: str,
) -> dict[str, object]:
    return {
        "id": message_id,
        "type": "message",
        "role": "assistant",
        "model": "mock-model",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


class _ScriptedAnthropic:
    """Real Anthropic client backed by scripted mocked HTTP responses."""

    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.requests: list[dict[str, object]] = []
        self._payloads = list(payloads)

        def handler(request: httpx2.Request) -> httpx2.Response:
            assert request.method == "POST"
            assert str(request.url) == f"{MOCK_BASE_URL}/v1/messages"
            self.requests.append(json.loads(request.content))
            if not self._payloads:
                raise AssertionError("Unexpected extra Anthropic request.")
            return httpx2.Response(200, json=self._payloads.pop(0))

        self.client = Anthropic(
            api_key="mock-key-not-a-credential",
            base_url=MOCK_BASE_URL,
            max_retries=0,
            http_client=httpx2.Client(
                transport=httpx2.MockTransport(handler),
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
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                "msg-1",
                [
                    _text_block("Let me calculate."),
                    _tool_use_block("toolu_1", "calculator", CALCULATOR_INPUT),
                ],
                "tool_use",
            ),
            _message_payload("msg-2", [_text_block("6 x 7 = 42")], "end_turn"),
        ]
    )

    result = run_anthropic_tool_use(
        provider.client,
        registry,
        model="mock-model",
        user_input="What is 6 times 7?",
    )

    first, second = provider.requests

    assert first == {
        "model": "mock-model",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "What is 6 times 7?"}],
        "tools": list(anthropic_tools(registry)),
    }
    assert second["tools"] == list(anthropic_tools(registry))
    assert second["messages"] == [
        {"role": "user", "content": "What is 6 times 7?"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me calculate."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "calculator",
                    "input": CALCULATOR_INPUT,
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": json.dumps(
                        {"operation": "multiply", "result": 42.0}
                    ),
                }
            ],
        },
    ]

    assert executed == ["calculator"]
    assert result == AnthropicToolUseResult(
        output_text="6 x 7 = 42",
        stop_reason="end_turn",
        executed_calls=(
            AnthropicToolUse(
                tool_use_id="toolu_1",
                name="calculator",
                arguments=CALCULATOR_INPUT,
            ),
        ),
        request_count=2,
    )


def test_request_loop_supports_multi_step_tool_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                "msg-1",
                [_tool_use_block("toolu_1", "calculator", CALCULATOR_INPUT)],
                "tool_use",
            ),
            _message_payload(
                "msg-2",
                [
                    _tool_use_block(
                        "toolu_2",
                        "calculator",
                        {"operation": "add", "left": 42, "right": 8},
                    )
                ],
                "tool_use",
            ),
            _message_payload("msg-3", [_text_block("50")], "end_turn"),
        ]
    )

    result = run_anthropic_tool_use(
        provider.client,
        registry,
        model="mock-model",
        user_input="Multiply 6 by 7, then add 8.",
    )

    assert executed == ["calculator", "calculator"]
    assert [len(request["messages"]) for request in provider.requests] == [
        1,
        3,
        5,
    ]
    assert result.output_text == "50"
    assert result.request_count == 3
    assert [call.tool_use_id for call in result.executed_calls] == [
        "toolu_1",
        "toolu_2",
    ]


def test_request_loop_returns_results_for_parallel_tool_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                "msg-1",
                [
                    _tool_use_block("toolu_1", "calculator", CALCULATOR_INPUT),
                    _tool_use_block(
                        "toolu_2", "note_lookup", {"key": "safety_rule"}
                    ),
                ],
                "tool_use",
            ),
            _message_payload("msg-2", [_text_block("done")], "end_turn"),
        ]
    )

    run_anthropic_tool_use(
        provider.client,
        registry,
        model="mock-model",
        user_input="Calculate and look up the safety rule.",
    )

    tool_results = provider.requests[1]["messages"][-1]["content"]

    assert executed == ["calculator", "note_lookup"]
    assert [block["tool_use_id"] for block in tool_results] == [
        "toolu_1",
        "toolu_2",
    ]
    assert all(block["type"] == "tool_result" for block in tool_results)


def test_request_loop_denies_invented_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                "msg-1",
                [_tool_use_block("toolu_1", "shell", {"command": "whoami"})],
                "tool_use",
            )
        ]
    )

    with pytest.raises(UnknownToolError):
        run_anthropic_tool_use(
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
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                "msg-1",
                [
                    _tool_use_block("toolu_1", "calculator", CALCULATOR_INPUT),
                    _tool_use_block(
                        "toolu_2",
                        "calculator",
                        {**CALCULATOR_INPUT, "command": "whoami"},
                    ),
                ],
                "tool_use",
            )
        ]
    )

    with pytest.raises(ToolValidationError):
        run_anthropic_tool_use(
            provider.client,
            registry,
            model="mock-model",
            user_input="Multiply.",
        )

    assert executed == []
    assert len(provider.requests) == 1


def test_request_loop_denies_schema_invalid_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                "msg-1",
                [
                    _tool_use_block(
                        "toolu_1",
                        "calculator",
                        {"operation": "power", "left": 2, "right": "64"},
                    )
                ],
                "tool_use",
            )
        ]
    )

    with pytest.raises(ToolValidationError):
        run_anthropic_tool_use(
            provider.client,
            registry,
            model="mock-model",
            user_input="Raise 2 to 64.",
        )

    assert executed == []


@pytest.mark.parametrize(
    "content",
    (
        [_tool_use_block("toolu_1", "calculator", "not-an-object")],
        [
            _tool_use_block("toolu_1", "calculator", CALCULATOR_INPUT),
            _tool_use_block("toolu_1", "calculator", CALCULATOR_INPUT),
        ],
        [
            {
                "type": "server_tool_use",
                "id": "srvtoolu_1",
                "name": "web_search",
                "input": {"query": "credentials"},
            }
        ],
    ),
    ids=("non-object-input", "duplicate-ids", "unrequested-server-tool"),
)
def test_request_loop_denies_malformed_or_unrequested_blocks(
    monkeypatch: pytest.MonkeyPatch,
    content: list[dict[str, object]],
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedAnthropic(
        [_message_payload("msg-1", content, "tool_use")]
    )

    with pytest.raises(AnthropicToolUseError):
        run_anthropic_tool_use(
            provider.client,
            registry,
            model="mock-model",
            user_input="Multiply.",
        )

    assert executed == []


@pytest.mark.parametrize(
    ("content", "stop_reason"),
    (
        ([_text_block("partial")], "max_tokens"),
        ([_text_block("no")], "refusal"),
        ([_text_block("paused")], "pause_turn"),
        ([_text_block("no tools")], "tool_use"),
        (
            [_tool_use_block("toolu_1", "calculator", CALCULATOR_INPUT)],
            "end_turn",
        ),
    ),
    ids=(
        "max-tokens",
        "refusal",
        "pause-turn",
        "tool-use-without-blocks",
        "terminal-with-tool-use",
    ),
)
def test_request_loop_fails_closed_on_inconsistent_stop(
    monkeypatch: pytest.MonkeyPatch,
    content: list[dict[str, object]],
    stop_reason: str,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedAnthropic(
        [_message_payload("msg-1", content, stop_reason)]
    )

    with pytest.raises(AnthropicToolUseError):
        run_anthropic_tool_use(
            provider.client,
            registry,
            model="mock-model",
            user_input="Multiply.",
        )

    assert executed == []
    assert len(provider.requests) == 1


def test_request_budget_terminates_endless_tool_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, executed = _spy_registry(monkeypatch)
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                f"msg-{index}",
                [
                    _tool_use_block(
                        f"toolu_{index}", "calculator", CALCULATOR_INPUT
                    )
                ],
                "tool_use",
            )
            for index in range(5)
        ]
    )

    with pytest.raises(AnthropicToolLoopBudgetError):
        run_anthropic_tool_use(
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
    provider = _ScriptedAnthropic(
        [
            _message_payload(
                "msg-1",
                [
                    _tool_use_block(
                        f"toolu_{index}", "calculator", CALCULATOR_INPUT
                    )
                    for index in range(3)
                ],
                "tool_use",
            )
        ]
    )

    with pytest.raises(AnthropicToolLoopBudgetError):
        run_anthropic_tool_use(
            provider.client,
            registry,
            model="mock-model",
            user_input="Calculate three times.",
            max_tool_calls=2,
        )

    assert executed == []


@pytest.mark.parametrize(
    ("max_tokens", "max_requests", "max_tool_calls"),
    (
        (0, 4, 8),
        (MAX_ANTHROPIC_OUTPUT_TOKENS + 1, 4, 8),
        (1024, 0, 8),
        (1024, MAX_ANTHROPIC_REQUESTS + 1, 8),
        (1024, True, 8),
        (1024, 4, 0),
        (1024, 4, MAX_ANTHROPIC_TOOL_CALLS + 1),
    ),
)
def test_request_loop_rejects_invalid_budgets(
    max_tokens: int,
    max_requests: int,
    max_tool_calls: int,
) -> None:
    provider = _ScriptedAnthropic([])

    with pytest.raises(ValueError):
        run_anthropic_tool_use(
            provider.client,
            build_default_registry(),
            model="mock-model",
            user_input="Multiply.",
            max_tokens=max_tokens,
            max_requests=max_requests,
            max_tool_calls=max_tool_calls,
        )

    assert provider.requests == []
