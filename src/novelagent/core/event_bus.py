"""Event bus: central pub/sub communication hub for all components."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

from novelagent.core.events import NarrativeEvent, SystemEvent

EventHandler = Callable[..., Awaitable[Any]]
"""Type alias for async event handlers."""


class EventBus:
    """In-memory async pub/sub event bus with branch-aware event storage.

    All components communicate through this bus. Events are stored in memory
    and can be queried by branch, type, or full history.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._events: list[SystemEvent | NarrativeEvent] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: SystemEvent | NarrativeEvent) -> None:
        """Publish an event: store it and notify all subscribers.

        The event's ``type`` field determines which subscribers are notified.
        Handlers subscribed to ``"*"`` receive all events.
        """
        async with self._lock:
            self._events.append(event)

        handlers = self._handlers.get(event.type, []) + self._handlers.get("*", [])
        for handler in handlers:
            await handler(event)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type.

        Use ``"*"`` as the event type to receive all events.
        """
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        self._handlers[event_type].remove(handler)

    async def get_branch_events(
        self, branch_id: str
    ) -> list[SystemEvent | NarrativeEvent]:
        """Return all events belonging to a specific branch, in order."""
        async with self._lock:
            return [e for e in self._events if e.branch_id == branch_id]

    async def get_events_by_type(
        self, event_type: str
    ) -> list[SystemEvent | NarrativeEvent]:
        """Return all events of a given type, in order."""
        async with self._lock:
            return [e for e in self._events if e.type == event_type]

    async def get_all_events(self) -> list[SystemEvent | NarrativeEvent]:
        """Return the full event history."""
        async with self._lock:
            return list(self._events)

    async def get_event_count(self) -> int:
        """Return total number of events published."""
        async with self._lock:
            return len(self._events)

    def clear(self) -> None:
        """Clear all events and handlers (primarily for testing)."""
        self._events.clear()
        self._handlers.clear()
