"""MemPalace integration layer for NovelAgent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from mempalace.knowledge_graph import KnowledgeGraph

# Default storage path inside the project data directory
DEFAULT_STORAGE_DIR = Path.cwd() / "data"
DEFAULT_DB_PATH = str(DEFAULT_STORAGE_DIR / "novelagent.sqlite3")


class EntityType(StrEnum):
    """Novel-specific entity types mapped onto the KG."""

    CHARACTER = "character"
    LOCATION = "location"
    ITEM = "item"
    FACTION = "faction"
    CONCEPT = "concept"
    EVENT_MARKER = "event_marker"

    @classmethod
    def novel_types(cls) -> list[str]:
        """Return all novel-specific entity type values."""
        return [m.value for m in cls]


@dataclass
class Entity:
    """A knowledge graph entity with its relationships."""

    id: str
    name: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)
    relations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Relation:
    """A typed relationship between two entities."""

    subject: str
    predicate: str
    object: str
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float = 1.0
    current: bool = True


class MemPalaceClient:
    """Client wrapping MemPalace's KnowledgeGraph for novel data.

    Provides novel-specific entity types (character, location, faction, …)
    and convenience CRUD methods on top of the temporal KG.
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = DEFAULT_DB_PATH
            DEFAULT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._kg = KnowledgeGraph(db_path)

    # ── Entity CRUD ───────────────────────────────────────────────────────

    def add_entity(
        self,
        name: str,
        entity_type: str = "unknown",
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Create or update an entity in the knowledge graph.

        Returns the entity's internal ID.
        """
        return self._kg.add_entity(name, entity_type, properties or {})

    def add_character(
        self, name: str, properties: dict[str, Any] | None = None
    ) -> str:
        """Convenience: add a character entity."""
        return self.add_entity(name, EntityType.CHARACTER, properties)

    def add_location(
        self, name: str, properties: dict[str, Any] | None = None
    ) -> str:
        """Convenience: add a location entity."""
        return self.add_entity(name, EntityType.LOCATION, properties)

    def add_faction(
        self, name: str, properties: dict[str, Any] | None = None
    ) -> str:
        """Convenience: add a faction/organization entity."""
        return self.add_entity(name, EntityType.FACTION, properties)

    def get_entity(self, name: str) -> Entity | None:
        """Look up an entity by display name, with its relations."""
        kg = self._kg
        eid = kg._entity_id(name)  # noqa: SLF001

        conn = kg._conn()  # noqa: SLF001
        row = conn.execute(
            "SELECT id, name, type, properties FROM entities WHERE id = ?",
            (eid,),
        ).fetchone()
        if row is None:
            return None

        props: dict[str, Any] = {}
        if row["properties"] and row["properties"] != "{}":
            props = json.loads(row["properties"])

        relations = kg.query_entity(name, direction="both")
        return Entity(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            properties=props,
            relations=relations,
        )

    def get_all_entities(
        self, entity_type: str | None = None
    ) -> list[Entity]:
        """List all entities, optionally filtered by type."""
        kg = self._kg
        conn = kg._conn()  # noqa: SLF001

        if entity_type:
            rows = conn.execute(
                "SELECT id, name, type, properties FROM entities WHERE type = ? ORDER BY name",
                (entity_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, type, properties FROM entities ORDER BY type, name"
            ).fetchall()

        results: list[Entity] = []
        for row in rows:
            props: dict[str, Any] = {}
            if row["properties"] and row["properties"] != "{}":
                props = json.loads(row["properties"])
            results.append(
                Entity(id=row["id"], name=row["name"], type=row["type"], properties=props)
            )
        return results

    def delete_entity(self, name: str) -> bool:
        """Delete an entity and all its relations.

        Returns True if the entity existed and was deleted.
        """
        kg = self._kg
        eid = kg._entity_id(name)  # noqa: SLF001

        conn = kg._conn()  # noqa: SLF001
        cursor = conn.execute("SELECT 1 FROM entities WHERE id = ?", (eid,))
        if cursor.fetchone() is None:
            return False

        conn.execute("DELETE FROM triples WHERE subject = ? OR object = ?", (eid, eid))
        conn.execute("DELETE FROM entities WHERE id = ?", (eid,))
        conn.commit()
        return True

    def entity_count(self) -> int:
        """Return total number of entities in the graph."""
        return self._kg.stats()["entities"]

    # ── Relation CRUD ─────────────────────────────────────────────────────

    def add_relation(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: str | None = None,
        valid_to: str | None = None,
        confidence: float = 1.0,
    ) -> str:
        """Add a relationship between two entities.

        Both entities are auto-created if they don't exist yet.
        Returns the triple ID.
        """
        return self._kg.add_triple(
            subject,
            predicate,
            obj,
            valid_from=valid_from,
            valid_to=valid_to,
            confidence=confidence,
        )

    def remove_relation(self, subject: str, predicate: str, obj: str) -> bool:
        """Permanently delete a relation triple.

        Returns True if at least one matching triple was removed.
        """
        kg = self._kg
        sub_id = kg._entity_id(subject)  # noqa: SLF001
        obj_id = kg._entity_id(obj)  # noqa: SLF001
        pred = predicate.lower().replace(" ", "_")

        conn = kg._conn()  # noqa: SLF001
        cursor = conn.execute(
            "DELETE FROM triples WHERE subject = ? AND predicate = ? AND object = ?",
            (sub_id, pred, obj_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def invalidate_relation(
        self, subject: str, predicate: str, obj: str, ended: str | None = None
    ) -> None:
        """Mark a relation as no longer valid (sets valid_to)."""
        self._kg.invalidate(subject, predicate, obj, ended=ended)

    def get_relations(
        self,
        entity_name: str | None = None,
        predicate: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query relations, optionally filtered by entity or predicate."""
        if predicate:
            return self._kg.query_relationship(predicate)
        if entity_name:
            return self._kg.query_entity(entity_name, direction="both")
        return []

    def relation_count(self) -> int:
        """Return total number of triples (current + expired)."""
        return self._kg.stats()["triples"]

    # ── Timeline ──────────────────────────────────────────────────────────

    def timeline(
        self, entity_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all facts in chronological order, optionally filtered by entity."""
        return self._kg.timeline(entity_name=entity_name)

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return storage statistics."""
        return self._kg.stats()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying database connection."""
        self._kg.close()
