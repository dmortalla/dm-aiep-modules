"""Tests for asynchronous event-driven workflow primitives."""

import pytest
from ai_engineering_foundations.events import (
    AsyncEventDispatcher,
    WorkflowEvent,
)
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_event_dispatcher_invokes_registered_handler() -> None:
    """Publishing an event should invoke its subscribed async handler."""
    dispatcher = AsyncEventDispatcher()
    received: list[WorkflowEvent] = []

    async def handle(event: WorkflowEvent) -> None:
        received.append(event)

    dispatcher.subscribe("llm.completed", handle)

    event = WorkflowEvent(
        name="llm.completed",
        payload={"provider": "openai"},
    )

    await dispatcher.publish(event)

    assert received == [event]


@pytest.mark.asyncio
async def test_event_dispatcher_preserves_handler_order() -> None:
    """Handlers should run deterministically in registration order."""
    dispatcher = AsyncEventDispatcher()
    calls: list[str] = []

    async def first(_: WorkflowEvent) -> None:
        calls.append("first")

    async def second(_: WorkflowEvent) -> None:
        calls.append("second")

    dispatcher.subscribe("workflow.completed", first)
    dispatcher.subscribe("workflow.completed", second)

    await dispatcher.publish(
        WorkflowEvent(name="workflow.completed", payload={})
    )

    assert calls == ["first", "second"]


@pytest.mark.asyncio
async def test_unsubscribed_event_is_safe() -> None:
    """Publishing an event with no subscribers should be a safe no-op."""
    dispatcher = AsyncEventDispatcher()

    await dispatcher.publish(
        WorkflowEvent(name="workflow.unhandled", payload={})
    )


def test_empty_event_name_subscription_is_rejected() -> None:
    """Subscriptions should reject empty event names."""
    dispatcher = AsyncEventDispatcher()

    async def handler(_: WorkflowEvent) -> None:
        return None

    with pytest.raises(ValueError, match="event_name"):
        dispatcher.subscribe("   ", handler)


def test_workflow_event_rejects_unknown_fields() -> None:
    """Workflow events should fail closed on unexpected fields."""
    with pytest.raises(ValidationError):
        WorkflowEvent(
            name="llm.completed",
            payload={},
            privileged_action="delete_credentials",
        )