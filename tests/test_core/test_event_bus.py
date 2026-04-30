"""Tests for the event bus (pub/sub + event storage)."""

import asyncio
from uuid import uuid4

import pytest

from novelagent.core import EventBus, EventType, NarrativeEvent, SystemEvent


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def sample_system_event() -> SystemEvent:
    return SystemEvent(type=EventType.SCENE_STARTED, source="test", payload={"ch": 1})


@pytest.fixture
def sample_narrative_event() -> NarrativeEvent:
    return NarrativeEvent(chapter=1, scene=1, content="Test narrative.")


class TestPublishAndSubscribe:
    """Basic publish/subscribe functionality."""

    async def test_publish_triggers_handler(self, bus: EventBus) -> None:
        received = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.SCENE_STARTED, handler)
        event = SystemEvent(type=EventType.SCENE_STARTED)
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].id == event.id

    async def test_publish_with_wildcard(self, bus: EventBus) -> None:
        received = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        bus.subscribe("*", handler)
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))
        await bus.publish(SystemEvent(type=EventType.NARRATIVE_ADVANCE))

        assert len(received) == 2

    async def test_handler_not_called_for_unsubscribed_type(
        self, bus: EventBus
    ) -> None:
        received = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.NARRATIVE_OUTPUT, handler)
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))

        assert len(received) == 0

    async def test_unsubscribe(self, bus: EventBus) -> None:
        received = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.SCENE_STARTED, handler)
        bus.unsubscribe(EventType.SCENE_STARTED, handler)
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))

        assert len(received) == 0

    async def test_multiple_handlers_same_type(self, bus: EventBus) -> None:
        received1 = []
        received2 = []

        async def handler1(event: SystemEvent) -> None:
            received1.append(event)

        async def handler2(event: SystemEvent) -> None:
            received2.append(event)

        bus.subscribe(EventType.SCENE_STARTED, handler1)
        bus.subscribe(EventType.SCENE_STARTED, handler2)
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))

        assert len(received1) == 1
        assert len(received2) == 1


class TestEventStorage:
    """Event storage and retrieval."""

    async def test_get_all_events(self, bus: EventBus) -> None:
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))
        await bus.publish(SystemEvent(type=EventType.NARRATIVE_ADVANCE))

        events = await bus.get_all_events()
        assert len(events) == 2

    async def test_get_event_count(self, bus: EventBus) -> None:
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))
        await bus.publish(SystemEvent(type=EventType.NARRATIVE_ADVANCE))
        assert await bus.get_event_count() == 2

    async def test_get_events_by_type(self, bus: EventBus) -> None:
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))
        await bus.publish(SystemEvent(type=EventType.NARRATIVE_ADVANCE))
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))

        scene_events = await bus.get_events_by_type(EventType.SCENE_STARTED)
        assert len(scene_events) == 2
        assert all(e.type == EventType.SCENE_STARTED for e in scene_events)

    async def test_events_are_ordered(self, bus: EventBus) -> None:
        e1 = SystemEvent(type=EventType.SCENE_STARTED)
        e2 = SystemEvent(type=EventType.NARRATIVE_ADVANCE)
        e3 = SystemEvent(type=EventType.NARRATIVE_OUTPUT)

        await bus.publish(e1)
        await bus.publish(e2)
        await bus.publish(e3)

        events = await bus.get_all_events()
        assert events[0].id == e1.id
        assert events[1].id == e2.id
        assert events[2].id == e3.id


class TestBranchFiltering:
    """Branch-aware event queries."""

    async def test_get_branch_events(self, bus: EventBus) -> None:
        await bus.publish(
            SystemEvent(type=EventType.SCENE_STARTED, branch_id="main")
        )
        await bus.publish(
            SystemEvent(type=EventType.NARRATIVE_ADVANCE, branch_id="feature-1")
        )
        await bus.publish(
            SystemEvent(type=EventType.SCENE_ENDED, branch_id="main")
        )

        main_events = await bus.get_branch_events("main")
        assert len(main_events) == 2
        assert all(e.branch_id == "main" for e in main_events)

        feature_events = await bus.get_branch_events("feature-1")
        assert len(feature_events) == 1
        assert feature_events[0].branch_id == "feature-1"

    async def test_branch_isolation(self, bus: EventBus) -> None:
        """Events in different branches don't leak into each other."""
        event_a = SystemEvent(
            type=EventType.SCENE_STARTED, payload={"ch": 1}, branch_id="branch-a"
        )
        event_b = SystemEvent(
            type=EventType.SCENE_STARTED, payload={"ch": 2}, branch_id="branch-b"
        )

        await bus.publish(event_a)
        await bus.publish(event_b)

        branch_a = await bus.get_branch_events("branch-a")
        assert len(branch_a) == 1
        assert branch_a[0].payload["ch"] == 1


class TestNarrativeEventSupport:
    """Event bus works with both event types."""

    async def test_publish_narrative_event(self, bus: EventBus) -> None:
        received = []

        async def handler(event: NarrativeEvent) -> None:
            received.append(event)

        bus.subscribe("*", handler)
        event = NarrativeEvent(chapter=1, scene=2, content="Hello world")

        await bus.publish(event)
        assert len(received) == 1
        assert received[0].content == "Hello world"

    async def test_mixed_event_types_storage(self, bus: EventBus) -> None:
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))
        await bus.publish(NarrativeEvent(content="Narrative text"))
        await bus.publish(SystemEvent(type=EventType.SCENE_ENDED))

        assert await bus.get_event_count() == 3


class TestClear:
    """Clear functionality."""

    async def test_clear_removes_all_events(self, bus: EventBus) -> None:
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))
        bus.clear()
        assert await bus.get_event_count() == 0

    async def test_clear_removes_handlers(self, bus: EventBus) -> None:
        received = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.SCENE_STARTED, handler)
        bus.clear()
        await bus.publish(SystemEvent(type=EventType.SCENE_STARTED))

        assert len(received) == 0


class TestConcurrency:
    """Basic async concurrency handling."""

    async def test_sequential_publishes_are_ordered(self, bus: EventBus) -> None:
        events = []
        for i in range(10):
            events.append(
                SystemEvent(
                    type=EventType.NARRATIVE_ADVANCE, payload={"seq": i}
                )
            )

        for e in events:
            await bus.publish(e)

        stored = await bus.get_all_events()
        for i, e in enumerate(stored):
            assert e.payload["seq"] == i

    async def test_concurrent_publishes(self, bus: EventBus) -> None:
        """Multiple concurrent publishes should not lose events."""

        async def publish_seq(start: int, count: int) -> None:
            for i in range(start, start + count):
                await bus.publish(
                    SystemEvent(
                        type=EventType.NARRATIVE_ADVANCE,
                        payload={"seq": i},
                    )
                )

        await asyncio.gather(
            publish_seq(0, 5),
            publish_seq(5, 5),
            publish_seq(10, 5),
        )

        assert await bus.get_event_count() == 15
