"""External framework integrations for Module 5."""

from ai_agent_engineering.integrations.langchain_agent import (
    build_langchain_agent,
    invoke_langchain_agent,
    registry_tool,
)

__all__ = [
    "build_langchain_agent",
    "invoke_langchain_agent",
    "registry_tool",
]
