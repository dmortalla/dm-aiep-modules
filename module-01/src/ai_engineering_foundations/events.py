"""Minimal asynchronous event-driven workflow primitives."""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


class WorkflowEvent(BaseModel):
    """Represent a validated event passed through an async workflow."""

    model_config = ConfigDict(extra="forbid")

    name: str
    payload: dict[str, Any]


EventHandler = Callable[[WorkflowEvent], Awaitable[None]]


class AsyncEventDispatcher:
    """Dispatch validated workflow events to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register an asynchronous handler for an event name."""
        if not event_name.strip():
            raise ValueError("event_name must not be empty")

        self._handlers[event_name].append(handler)

    async def publish(self, event: WorkflowEvent) -> None:
        """Dispatch an event to its handlers in registration order."""
        for handler in self._handlers.get(event.name, []):
            await handler(event)