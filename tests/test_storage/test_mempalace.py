"""Tests for MemPalaceClient integration layer."""

import pytest

from novelagent.storage import Entity, EntityType, MemPalaceClient


@pytest.fixture
def client() -> MemPalaceClient:
    """Create an in-memory MemPalaceClient for testing."""
    c = MemPalaceClient(db_path=":memory:")
    yield c
    c.close()


class TestEntityCRUD:
    """Entity creation, retrieval, listing, and deletion."""

    def test_add_entity(self, client: MemPalaceClient) -> None:
        eid = client.add_entity("Alice", "character", {"age": 30, "title": "Hero"})
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_get_entity(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character", {"age": 30})
        entity = client.get_entity("Alice")

        assert entity is not None
        assert entity.name == "Alice"
        assert entity.type == "character"
        assert entity.properties["age"] == 30

    def test_get_nonexistent_entity(self, client: MemPalaceClient) -> None:
        entity = client.get_entity("Nonexistent")
        assert entity is None

    def test_get_all_entities(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character")
        client.add_entity("Bob", "character")
        client.add_entity("Castle", "location")

        all_entities = client.get_all_entities()
        assert len(all_entities) == 3

    def test_get_entities_by_type(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character")
        client.add_entity("Bob", "character")
        client.add_entity("Castle", "location")

        chars = client.get_all_entities(entity_type="character")
        assert len(chars) == 2
        assert all(e.type == "character" for e in chars)

        locs = client.get_all_entities(entity_type="location")
        assert len(locs) == 1
        assert locs[0].name == "Castle"

    def test_delete_entity(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character")
        assert client.entity_count() == 1

        result = client.delete_entity("Alice")
        assert result is True
        assert client.entity_count() == 0

    def test_delete_nonexistent_entity(self, client: MemPalaceClient) -> None:
        result = client.delete_entity("Nonexistent")
        assert result is False

    def test_delete_entity_removes_relations(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character")
        client.add_entity("Bob", "character")
        client.add_relation("Alice", "loves", "Bob")

        client.delete_entity("Alice")
        assert client.entity_count() == 1
        assert client.relation_count() == 0

    def test_entity_with_no_properties(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character")
        entity = client.get_entity("Alice")
        assert entity is not None
        assert entity.properties == {}

    def test_entity_properties_roundtrip(self, client: MemPalaceClient) -> None:
        props = {"age": 25, "occupation": "Knight", "skills": ["sword", "horse"]}
        client.add_entity("Alice", "character", props)
        entity = client.get_entity("Alice")
        assert entity is not None
        assert entity.properties["age"] == 25
        assert entity.properties["occupation"] == "Knight"
        assert entity.properties["skills"] == ["sword", "horse"]

    def test_update_entity_properties(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character", {"age": 30})
        client.add_entity("Alice", "character", {"age": 31})
        entity = client.get_entity("Alice")
        assert entity is not None
        assert entity.properties["age"] == 31

    def test_entity_count(self, client: MemPalaceClient) -> None:
        assert client.entity_count() == 0
        client.add_entity("Alice", "character")
        client.add_entity("Bob", "character")
        assert client.entity_count() == 2


class TestEntityTypeHelpers:
    """Convenience methods for novel entity types."""

    def test_add_character(self, client: MemPalaceClient) -> None:
        client.add_character("Alice", {"age": 30})
        entity = client.get_entity("Alice")
        assert entity is not None
        assert entity.type == "character"

    def test_add_location(self, client: MemPalaceClient) -> None:
        client.add_location("Castle", {"region": "north"})
        entity = client.get_entity("Castle")
        assert entity is not None
        assert entity.type == "location"
        assert entity.properties["region"] == "north"

    def test_add_faction(self, client: MemPalaceClient) -> None:
        client.add_faction("Rebels", {"motto": "Freedom"})
        entity = client.get_entity("Rebels")
        assert entity is not None
        assert entity.type == "faction"
        assert entity.properties["motto"] == "Freedom"

    def test_entity_type_enum_values(self) -> None:
        assert EntityType.CHARACTER.value == "character"
        assert EntityType.LOCATION.value == "location"
        assert EntityType.ITEM.value == "item"
        assert EntityType.FACTION.value == "faction"
        assert EntityType.CONCEPT.value == "concept"
        assert EntityType.EVENT_MARKER.value == "event_marker"

    def test_novel_types_classmethod(self) -> None:
        types = EntityType.novel_types()
        assert "character" in types
        assert "location" in types
        assert "faction" in types
        assert len(types) == 6


class TestRelationCRUD:
    """Relationship creation, query, and removal."""

    def test_add_relation(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character")
        client.add_entity("Bob", "character")
        tid = client.add_relation("Alice", "loves", "Bob")
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_add_relation_auto_creates_entities(self, client: MemPalaceClient) -> None:
        """Relations auto-create entities if they don't exist."""
        client.add_relation("Alice", "loves", "Bob")
        assert client.entity_count() == 2

    def test_get_relations_by_entity(self, client: MemPalaceClient) -> None:
        client.add_relation("Alice", "loves", "Bob")
        client.add_relation("Alice", "works_with", "Charlie")

        relations = client.get_relations(entity_name="Alice")
        assert len(relations) == 2

    def test_get_relations_by_predicate(self, client: MemPalaceClient) -> None:
        client.add_relation("Alice", "loves", "Bob")
        client.add_relation("Charlie", "loves", "Diana")
        client.add_relation("Alice", "works_with", "Charlie")

        loves = client.get_relations(predicate="loves")
        assert len(loves) == 2

        works = client.get_relations(predicate="works_with")
        assert len(works) == 1

    def test_get_relations_no_filters(self, client: MemPalaceClient) -> None:
        assert client.get_relations() == []

    def test_remove_relation(self, client: MemPalaceClient) -> None:
        client.add_relation("Alice", "loves", "Bob")
        assert client.relation_count() == 1

        result = client.remove_relation("Alice", "loves", "Bob")
        assert result is True
        assert client.relation_count() == 0

    def test_remove_nonexistent_relation(self, client: MemPalaceClient) -> None:
        result = client.remove_relation("Alice", "loves", "Bob")
        assert result is False

    def test_invalidate_relation(self, client: MemPalaceClient) -> None:
        client.add_relation("Alice", "loves", "Bob", valid_from="2024-01-01")
        client.invalidate_relation("Alice", "loves", "Bob", ended="2025-01-01")

        relations = client.get_relations(entity_name="Alice")
        assert len(relations) == 1
        assert relations[0]["valid_to"] == "2025-01-01"
        assert relations[0]["current"] is False

    def test_relation_count(self, client: MemPalaceClient) -> None:
        assert client.relation_count() == 0
        client.add_relation("Alice", "loves", "Bob")
        client.add_relation("Bob", "loves", "Alice")
        assert client.relation_count() == 2

    def test_duplicate_relation_not_recreated(self, client: MemPalaceClient) -> None:
        """Adding the same active relation twice should return existing ID."""
        tid1 = client.add_relation("Alice", "loves", "Bob")
        tid2 = client.add_relation("Alice", "loves", "Bob")
        assert tid1 == tid2
        assert client.relation_count() == 1

    def test_relation_predicate_normalization(self, client: MemPalaceClient) -> None:
        """Predicates are normalized to lowercase with underscores."""
        client.add_relation("Alice", "Is In Love With", "Bob")
        relations = client.get_relations(entity_name="Alice")
        assert relations[0]["predicate"] == "is_in_love_with"


class TestTimeline:
    """Timeline queries."""

    def test_timeline_all(self, client: MemPalaceClient) -> None:
        client.add_relation("Alice", "born", "1990", valid_from="1990-01-01")
        client.add_relation("Alice", "meets", "Bob", valid_from="2010-06-15")

        tl = client.timeline()
        assert len(tl) == 2

    def test_timeline_filtered(self, client: MemPalaceClient) -> None:
        client.add_relation("Alice", "born", "1990", valid_from="1990-01-01")
        client.add_relation("Bob", "born", "1992", valid_from="1992-03-20")

        tl = client.timeline(entity_name="Alice")
        assert len(tl) == 1
        assert tl[0]["subject"] == "Alice"  # display name


class TestStats:
    """Storage statistics."""

    def test_stats(self, client: MemPalaceClient) -> None:
        client.add_entity("Alice", "character")
        client.add_relation("Alice", "loves", "Bob")

        s = client.stats()
        assert s["entities"] == 2  # Alice + Bob (auto-created)
        assert s["triples"] == 1
        assert s["current_facts"] == 1
        assert "relationship_types" in s


class TestLifecycle:
    """Client lifecycle."""

    def test_close(self, client: MemPalaceClient) -> None:
        """Close should not raise."""
        client.close()

    def test_multiple_clients_isolated(self) -> None:
        """Different in-memory databases should not share data."""
        c1 = MemPalaceClient(db_path=":memory:")
        c2 = MemPalaceClient(db_path=":memory:")

        c1.add_entity("Alice", "character")
        assert c1.entity_count() == 1
        assert c2.entity_count() == 0

        c1.close()
        c2.close()
