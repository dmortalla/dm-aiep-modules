"""Tests proving genuine LangChain agent and tool execution."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from ai_agent_engineering.integrations import (
    build_langchain_agent,
    invoke_langchain_agent,
)
from ai_agent_engineering.tools.builtins import build_default_registry
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import (
    BaseChatModel,
    LangSmithParams,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable


class DeterministicToolCallingModel(BaseChatModel):
    """Local deterministic model that genuinely participates in tool calling."""

    bound_tool_names: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "module-05-deterministic-tool-calling-model"

    def _get_ls_params(
        self,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LangSmithParams:
        return LangSmithParams(
            ls_provider="module-05-local",
            ls_model_name="deterministic",
            ls_model_type="chat",
        )

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        del tool_choice, kwargs

        names: list[str] = []

        for tool in tools:
            if hasattr(tool, "name"):
                names.append(tool.name)
            elif isinstance(tool, dict):
                function = tool.get("function", {})
                name = function.get("name")
                if name:
                    names.append(name)

        return self.model_copy(
            update={"bound_tool_names": names},
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs

        tool_messages = [
            message
            for message in messages
            if isinstance(message, ToolMessage)
        ]

        if not tool_messages:
            if "calculator" not in self.bound_tool_names:
                raise AssertionError(
                    "LangChain did not bind the calculator tool."
                )

            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculator",
                        "args": {
                            "operation": "multiply",
                            "left": 6,
                            "right": 7,
                        },
                        "id": "module5-call-1",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            observation = str(tool_messages[-1].content)

            message = AIMessage(
                content=f"Observed calculator result: {observation}",
            )

        return ChatResult(
            generations=[
                ChatGeneration(message=message),
            ]
        )


def test_langchain_agent_executes_registry_tool() -> None:
    registry = build_default_registry()
    model = DeterministicToolCallingModel()

    agent = build_langchain_agent(
        model=model,
        registry=registry,
    )

    result = invoke_langchain_agent(
        agent,
        goal="Calculate six times seven.",
    )

    messages = result["messages"]

    tool_messages = [
        message
        for message in messages
        if isinstance(message, ToolMessage)
    ]

    assert len(tool_messages) == 1
    assert "42" in str(tool_messages[0].content)

    final_message = messages[-1]

    assert isinstance(final_message, AIMessage)
    assert "42" in str(final_message.content)


def test_langchain_agent_receives_only_allowlisted_registry_tools() -> None:
    registry = build_default_registry()
    model = DeterministicToolCallingModel()

    agent = build_langchain_agent(
        model=model,
        registry=registry,
    )

    result = invoke_langchain_agent(
        agent,
        goal="Calculate six times seven.",
    )

    assert "42" in str(result["messages"][-1].content)


def test_empty_goal_is_rejected_before_agent_execution() -> None:
    registry = build_default_registry()
    model = DeterministicToolCallingModel()

    agent = build_langchain_agent(
        model=model,
        registry=registry,
    )

    with pytest.raises(ValueError, match="goal cannot be empty"):
        invoke_langchain_agent(
            agent,
            goal="   ",
        )
