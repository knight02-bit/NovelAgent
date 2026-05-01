"""Tests for the Knowledge Graph service layer."""

import pytest

from novelagent.core import EventBus, EventType, SystemEvent
from novelagent.kg import KnowledgeGraphService, ValidationError
from novelagent.storage import EntityType


@pytest.fixture
def kg() -> KnowledgeGraphService:
    """In-memory KG service without event bus."""
    svc = KnowledgeGraphService(db_path=":memory:")
    yield svc
    svc.close()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def kg_with_bus(bus: EventBus) -> KnowledgeGraphService:
    """KG service connected to an event bus."""
    svc = KnowledgeGraphService(db_path=":memory:", event_bus=bus)
    yield svc
    svc.close()


# ── Entity Operations ───────────────────────────────────────────────────


class TestCreateEntity:
    """Entity creation with and without event bus."""

    async def test_create_character(self, kg: KnowledgeGraphService) -> None:
        entity = await kg.create_entity("Alice", "character", {"age": 30})
        assert entity.name == "Alice"
        assert entity.type == "character"
        assert entity.properties["age"] == 30
        assert entity.id is not None

    async def test_create_location(self, kg: KnowledgeGraphService) -> None:
        entity = await kg.create_entity(
            "Castle", "location", {"region": "north"}
        )
        assert entity.name == "Castle"
        assert entity.type == "location"
        assert entity.properties["region"] == "north"

    async def test_create_entity_without_properties(
        self, kg: KnowledgeGraphService
    ) -> None:
        entity = await kg.create_entity("Bob", "character")
        assert entity.name == "Bob"
        assert entity.properties == {}

    async def test_create_unknown_type_allowed(
        self, kg: KnowledgeGraphService
    ) -> None:
        entity = await kg.create_entity("Mystery", "unknown")
        assert entity.type == "unknown"

    async def test_create_invalid_type_raises(
        self, kg: KnowledgeGraphService
    ) -> None:
        with pytest.raises(ValidationError, match="Unknown entity type"):
            await kg.create_entity("Bad", "invalid_type")

    async def test_create_emits_event(self, kg_with_bus: KnowledgeGraphService, bus: EventBus) -> None:
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe(EventType.CHARACTER_STATE_CHANGED, handler)

        await kg_with_bus.create_entity("Alice", "character")
        assert len(events) == 1
        assert events[0].payload["operation"] == "create_entity"
        assert events[0].payload["entity_name"] == "Alice"

    async def test_create_character_emits_character_event(
        self, kg_with_bus: KnowledgeGraphService, bus: EventBus
    ) -> None:
        """Creating a character entity emits CHARACTER_STATE_CHANGED."""
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe(EventType.CHARACTER_STATE_CHANGED, handler)

        await kg_with_bus.create_entity("Alice", "character")
        assert len(events) == 1

        await kg_with_bus.create_entity("Castle", "location")
        # Second event should be KG_QUERY_RESULT, not CHARACTER_STATE_CHANGED
        assert len(events) == 1


class TestGetEntity:
    """Entity retrieval."""

    async def test_get_existing(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character", {"age": 30})
        entity = await kg.get_entity("Alice")
        assert entity is not None
        assert entity.name == "Alice"
        assert entity.properties["age"] == 30

    async def test_get_nonexistent(self, kg: KnowledgeGraphService) -> None:
        entity = await kg.get_entity("Nobody")
        assert entity is None

    async def test_get_entities_all(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Bob", "character")
        await kg.create_entity("Castle", "location")

        all_entities = await kg.get_entities()
        assert len(all_entities) == 3

    async def test_get_entities_by_type(
        self, kg: KnowledgeGraphService
    ) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Bob", "character")
        await kg.create_entity("Castle", "location")

        chars = await kg.get_entities(entity_type="character")
        assert len(chars) == 2

        locs = await kg.get_entities(entity_type="location")
        assert len(locs) == 1


class TestUpdateEntity:
    """Entity property updates."""

    async def test_update_existing(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character", {"age": 30})
        updated = await kg.update_entity("Alice", {"age": 31, "title": "Hero"})
        assert updated is not None
        assert updated.properties["age"] == 31
        assert updated.properties["title"] == "Hero"

    async def test_update_nonexistent(self, kg: KnowledgeGraphService) -> None:
        result = await kg.update_entity("Nobody", {"age": 25})
        assert result is None

    async def test_update_merge_preserves_extra_keys(
        self, kg: KnowledgeGraphService
    ) -> None:
        await kg.create_entity("Alice", "character", {"age": 30})
        await kg.update_entity("Alice", {"title": "Hero"})
        entity = await kg.get_entity("Alice")
        assert entity is not None
        assert entity.properties["age"] == 30
        assert entity.properties["title"] == "Hero"

    async def test_update_emits_event(
        self, kg_with_bus: KnowledgeGraphService, bus: EventBus
    ) -> None:
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe(EventType.CHARACTER_STATE_CHANGED, handler)

        await kg_with_bus.create_entity("Alice", "character")
        events.clear()
        await kg_with_bus.update_entity("Alice", {"age": 31})

        assert len(events) == 1
        assert events[0].payload["operation"] == "update_entity"


class TestDeleteEntity:
    """Entity deletion."""

    async def test_delete_existing(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        assert await kg.entity_count() == 1

        result = await kg.delete_entity("Alice")
        assert result is True
        assert await kg.entity_count() == 0

    async def test_delete_nonexistent(self, kg: KnowledgeGraphService) -> None:
        result = await kg.delete_entity("Nobody")
        assert result is False

    async def test_delete_emits_event(
        self, kg_with_bus: KnowledgeGraphService, bus: EventBus
    ) -> None:
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe(EventType.CHARACTER_STATE_CHANGED, handler)

        await kg_with_bus.create_entity("Alice", "character")
        events.clear()
        await kg_with_bus.delete_entity("Alice")

        assert len(events) == 1
        assert events[0].payload["operation"] == "delete_entity"


# ── Relation Operations ─────────────────────────────────────────────────


class TestCreateRelation:
    """Relation creation."""

    async def test_create_relation(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Bob", "character")
        tid = await kg.create_relation("Alice", "loves", "Bob")
        assert isinstance(tid, str)
        assert len(tid) > 0

    async def test_create_relation_auto_creates_entities(
        self, kg: KnowledgeGraphService
    ) -> None:
        tid = await kg.create_relation("Alice", "loves", "Bob")
        assert await kg.entity_count() == 2

    async def test_create_relation_emits_event(
        self, kg_with_bus: KnowledgeGraphService, bus: EventBus
    ) -> None:
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe(EventType.RELATION_CHANGED, handler)

        await kg_with_bus.create_relation("Alice", "loves", "Bob")
        assert len(events) == 1
        assert events[0].payload["operation"] == "create_relation"


class TestGetRelation:
    """Relation queries."""

    async def test_get_relations_by_entity(
        self, kg: KnowledgeGraphService
    ) -> None:
        await kg.create_relation("Alice", "loves", "Bob")
        await kg.create_relation("Alice", "works_with", "Charlie")

        relations = await kg.get_relations(entity_name="Alice")
        assert len(relations) == 2

    async def test_get_relations_by_predicate(
        self, kg: KnowledgeGraphService
    ) -> None:
        await kg.create_relation("Alice", "loves", "Bob")
        await kg.create_relation("Charlie", "loves", "Diana")

        relations = await kg.get_relations(predicate="loves")
        assert len(relations) == 2

    async def test_get_relations_empty(self, kg: KnowledgeGraphService) -> None:
        assert await kg.get_relations() == []


class TestRemoveRelation:
    """Relation removal."""

    async def test_remove_existing(self, kg: KnowledgeGraphService) -> None:
        await kg.create_relation("Alice", "loves", "Bob")
        assert await kg.relation_count() == 1

        result = await kg.remove_relation("Alice", "loves", "Bob")
        assert result is True
        assert await kg.relation_count() == 0

    async def test_remove_nonexistent(self, kg: KnowledgeGraphService) -> None:
        result = await kg.remove_relation("Alice", "loves", "Bob")
        assert result is False

    async def test_remove_emits_event(
        self, kg_with_bus: KnowledgeGraphService, bus: EventBus
    ) -> None:
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe(EventType.RELATION_CHANGED, handler)

        await kg_with_bus.create_relation("Alice", "loves", "Bob")
        events.clear()
        await kg_with_bus.remove_relation("Alice", "loves", "Bob")

        assert len(events) == 1
        assert events[0].payload["operation"] == "remove_relation"

    async def test_invalidate_relation(
        self, kg: KnowledgeGraphService
    ) -> None:
        await kg.create_relation(
            "Alice", "loves", "Bob", valid_from="2024-01-01"
        )
        await kg.invalidate_relation(
            "Alice", "loves", "Bob", ended="2025-01-01"
        )

        relations = await kg.get_relations(entity_name="Alice")
        assert len(relations) == 1
        assert relations[0]["valid_to"] == "2025-01-01"


# ── Novel-Specific Queries ──────────────────────────────────────────────


class TestStoryCast:
    """Character-specific queries."""

    async def test_get_story_cast(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Bob", "character")
        await kg.create_entity("Castle", "location")

        cast = await kg.get_story_cast()
        assert len(cast) == 2
        assert all(e.type == "character" for e in cast)

    async def test_get_locations(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Castle", "location")
        await kg.create_entity("Forest", "location")

        locs = await kg.get_locations()
        assert len(locs) == 2
        assert all(e.type == "location" for e in locs)

    async def test_get_factions(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Rebels", "faction")
        await kg.create_entity("Empire", "faction")

        factions = await kg.get_factions()
        assert len(factions) == 2


class TestEntityNetwork:
    """Entity network (depth) queries."""

    async def test_network_depth_1(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Bob", "character")
        await kg.create_relation("Alice", "loves", "Bob")

        network = await kg.get_entity_network("Alice", depth=1)
        assert network["center"] is not None
        assert network["center"]["name"] == "Alice"
        assert len(network["relations"]) == 1
        # depth=1 means no neighbours expanded
        assert len(network["neighbours"]) == 0

    async def test_network_depth_2(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Bob", "character")
        await kg.create_entity("Charlie", "character")
        await kg.create_relation("Alice", "loves", "Bob")
        await kg.create_relation("Bob", "works_with", "Charlie")

        network = await kg.get_entity_network("Alice", depth=2)
        assert network["center"] is not None
        assert len(network["relations"]) == 1
        # depth=2: Bob is a neighbour, his relations are expanded
        assert len(network["neighbours"]) == 1
        # Bob should have relations to both Alice and Charlie (bidirectional query)
        bob = network["neighbours"][0]
        assert bob["entity"]["name"] == "Bob"
        assert len(bob["relations"]) == 2

    async def test_network_nonexistent(self, kg: KnowledgeGraphService) -> None:
        network = await kg.get_entity_network("Nobody")
        assert network["center"] is None


class TestSearch:
    """Entity search."""

    async def test_search_by_name(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Alexander", "character")
        await kg.create_entity("Bob", "character")

        results = await kg.search_entities("alice")
        assert len(results) == 1
        assert results[0].name == "Alice"

        results = await kg.search_entities("al")
        assert len(results) == 2  # Alice, Alexander

    async def test_search_with_type_filter(
        self, kg: KnowledgeGraphService
    ) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_entity("Castle", "location")

        results = await kg.search_entities("al", entity_type="character")
        assert len(results) == 1
        assert results[0].type == "character"

    async def test_search_no_results(self, kg: KnowledgeGraphService) -> None:
        results = await kg.search_entities("nonexistent")
        assert results == []


class TestRelationMap:
    """Relation map queries (only relations between listed entities)."""

    async def test_relation_map(self, kg: KnowledgeGraphService) -> None:
        await kg.create_relation("Alice", "loves", "Bob")
        await kg.create_relation("Bob", "works_with", "Charlie")
        await kg.create_relation("Alice", "knows", "Charlie")

        rm = await kg.get_relation_map(["Alice", "Bob", "Charlie"])
        assert len(rm["entities"]) == 3
        # All three relations connect entities in the list
        assert len(rm["relations"]) == 3

    async def test_relation_map_filters_external(
        self, kg: KnowledgeGraphService
    ) -> None:
        await kg.create_relation("Alice", "loves", "Bob")
        await kg.create_relation("Alice", "knows", "Stranger")

        rm = await kg.get_relation_map(["Alice", "Bob"])
        assert len(rm["entities"]) == 2
        # Only relation between Alice and Bob is included
        assert len(rm["relations"]) == 1
        assert rm["relations"][0]["predicate"] == "loves"

    async def test_relation_map_nonexistent(
        self, kg: KnowledgeGraphService
    ) -> None:
        rm = await kg.get_relation_map(["Nobody"])
        assert rm["entities"] == []
        assert rm["relations"] == []


# ── Stats and Lifecycle ─────────────────────────────────────────────────


class TestStats:
    """KG service statistics."""

    async def test_stats(self, kg: KnowledgeGraphService) -> None:
        await kg.create_entity("Alice", "character")
        await kg.create_relation("Alice", "loves", "Bob")

        s = kg.stats()
        assert s["entities"] >= 2
        assert s["triples"] >= 1


class TestLifecycle:
    """Service lifecycle."""

    async def test_close(self, kg: KnowledgeGraphService) -> None:
        kg.close()  # should not raise

    async def test_no_event_bus_by_default(
        self, kg: KnowledgeGraphService
    ) -> None:
        """Service works without an event bus."""
        entity = await kg.create_entity("Alice", "character")
        assert entity.name == "Alice"


class TestEventBusIntegration:
    """End-to-end event bus integration."""

    async def test_no_events_without_bus(
        self, kg: KnowledgeGraphService, bus: EventBus
    ) -> None:
        """When no bus is provided, no events should be published."""
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe("*", handler)

        # Use a service *without* bus
        await kg.create_entity("Alice", "character")
        assert len(events) == 0

    async def test_all_mutation_events(
        self, kg_with_bus: KnowledgeGraphService, bus: EventBus
    ) -> None:
        """All mutation operations emit events."""
        events = []

        async def handler(event: SystemEvent) -> None:
            events.append(event)

        bus.subscribe("*", handler)

        await kg_with_bus.create_entity("Alice", "character")
        await kg_with_bus.create_relation("Alice", "loves", "Bob")
        await kg_with_bus.update_entity("Alice", {"age": 30})
        await kg_with_bus.remove_relation("Alice", "loves", "Bob")

        assert len(events) == 4
