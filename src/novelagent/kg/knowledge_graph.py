"""Knowledge Graph service layer for novel-specific operations.

Builds on MemPalaceClient, adds event integration, type validation,
and rich query APIs for the novel domain.
"""

from __future__ import annotations

from typing import Any

from novelagent.core import EventBus, EventType, SystemEvent
from novelagent.storage import (
    Entity,
    EntityType,
    MemPalaceClient,
)


class ValidationError(Exception):
    """Raised when an entity or relation operation violates validation rules."""


class KnowledgeGraphService:
    """High-level KG operations with event bus integration.

    Each mutation publishes a corresponding system event so that other
    components (Agent Core, GUI, Plot Engine) can react to changes.
    """

    def __init__(
        self,
        db_path: str | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._client = MemPalaceClient(db_path)
        self._event_bus = event_bus

    # ── Entity Operations ─────────────────────────────────────────────────

    async def create_entity(
        self,
        name: str,
        entity_type: str = "unknown",
        properties: dict[str, Any] | None = None,
        source: str = "user",
    ) -> Entity:
        """Create a new entity or update an existing one.

        Validates that ``entity_type`` is one of the known novel types
        unless it is ``"unknown"``.
        """
        self._validate_entity_type(entity_type)
        cleaned = properties or {}
        self._client.add_entity(name, entity_type, cleaned)
        entity = self._client.get_entity(name)
        assert entity is not None  # just created

        await self._emit_event(
            EventType.CHARACTER_STATE_CHANGED
            if entity_type == EntityType.CHARACTER
            else EventType.KG_QUERY_RESULT,
            payload={
                "operation": "create_entity",
                "entity_id": entity.id,
                "entity_name": name,
                "entity_type": entity_type,
                "properties": cleaned,
            },
            source=source,
        )
        return entity

    async def get_entity(self, name: str) -> Entity | None:
        """Look up an entity by display name, with relations."""
        return self._client.get_entity(name)

    async def get_entities(
        self, entity_type: str | None = None
    ) -> list[Entity]:
        """List all entities, optionally filtered by type."""
        return self._client.get_all_entities(entity_type)

    async def update_entity(
        self,
        name: str,
        properties: dict[str, Any],
        source: str = "user",
    ) -> Entity | None:
        """Update an entity's properties.

        If the entity does not exist, returns ``None``.
        """
        existing = self._client.get_entity(name)
        if existing is None:
            return None

        merged = {**existing.properties, **properties}
        self._client.add_entity(name, existing.type, merged)
        updated = self._client.get_entity(name)

        await self._emit_event(
            EventType.CHARACTER_STATE_CHANGED
            if existing.type == EntityType.CHARACTER
            else EventType.KG_QUERY_RESULT,
            payload={
                "operation": "update_entity",
                "entity_name": name,
                "entity_type": existing.type,
                "previous": existing.properties,
                "current": merged,
            },
            source=source,
        )
        return updated

    async def delete_entity(
        self, name: str, source: str = "user"
    ) -> bool:
        """Delete an entity and all its relations.

        Returns ``True`` if the entity existed.
        """
        entity = self._client.get_entity(name)
        if entity is None:
            return False

        result = self._client.delete_entity(name)

        await self._emit_event(
            EventType.CHARACTER_STATE_CHANGED
            if entity.type == EntityType.CHARACTER
            else EventType.KG_QUERY_RESULT,
            payload={
                "operation": "delete_entity",
                "entity_name": name,
                "entity_type": entity.type,
            },
            source=source,
        )
        return result

    async def entity_count(self) -> int:
        """Return the total number of entities."""
        return self._client.entity_count()

    # ── Relation Operations ───────────────────────────────────────────────

    async def create_relation(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: str | None = None,
        valid_to: str | None = None,
        confidence: float = 1.0,
        source: str = "user",
    ) -> str:
        """Add a relationship between two entities.

        Both entities are auto-created if they do not exist.
        Returns the triple ID.
        """
        triple_id = self._client.add_relation(
            subject, predicate, obj,
            valid_from=valid_from,
            valid_to=valid_to,
            confidence=confidence,
        )

        await self._emit_event(
            EventType.RELATION_CHANGED,
            payload={
                "operation": "create_relation",
                "triple_id": triple_id,
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "valid_from": valid_from,
                "valid_to": valid_to,
            },
            source=source,
        )
        return triple_id

    async def get_relations(
        self,
        entity_name: str | None = None,
        predicate: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query relations, optionally filtered by entity or predicate."""
        return self._client.get_relations(
            entity_name=entity_name, predicate=predicate
        )

    async def remove_relation(
        self,
        subject: str,
        predicate: str,
        obj: str,
        source: str = "user",
    ) -> bool:
        """Permanently delete a relation triple."""
        result = self._client.remove_relation(subject, predicate, obj)

        if result:
            await self._emit_event(
                EventType.RELATION_CHANGED,
                payload={
                    "operation": "remove_relation",
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                },
                source=source,
            )
        return result

    async def invalidate_relation(
        self,
        subject: str,
        predicate: str,
        obj: str,
        ended: str | None = None,
        source: str = "user",
    ) -> None:
        """Mark a relation as no longer valid (sets valid_to)."""
        self._client.invalidate_relation(subject, predicate, obj, ended=ended)

        await self._emit_event(
            EventType.RELATION_CHANGED,
            payload={
                "operation": "invalidate_relation",
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "ended": ended,
            },
            source=source,
        )

    async def relation_count(self) -> int:
        """Return the total number of triples."""
        return self._client.relation_count()

    # ── Novel-Specific Queries ────────────────────────────────────────────

    async def get_story_cast(self) -> list[Entity]:
        """Return all character entities (the story cast)."""
        return self._client.get_all_entities(
            entity_type=EntityType.CHARACTER
        )

    async def get_locations(self) -> list[Entity]:
        """Return all location entities."""
        return self._client.get_all_entities(
            entity_type=EntityType.LOCATION
        )

    async def get_factions(self) -> list[Entity]:
        """Return all faction / organisation entities."""
        return self._client.get_all_entities(
            entity_type=EntityType.FACTION
        )

    async def get_entity_network(
        self, name: str, depth: int = 1
    ) -> dict[str, Any]:
        """Get an entity together with its relation network.

        ``depth=1`` returns the entity and its direct neighbours.
        Returns a dict with ``"center"``, ``"relations"``, and
        ``"neighbours"`` (each neighbour includes its own relations).
        """
        entity = self._client.get_entity(name)
        if entity is None:
            return {"center": None, "relations": [], "neighbours": []}

        relations = self._client.get_relations(entity_name=name)
        neighbours: list[dict[str, Any]] = []

        if depth > 1:
            seen = {name.lower().replace(" ", "_")}
            for rel in relations:
                for side in ("subject", "object"):
                    other = rel[side]
                    other_id = other.lower().replace(" ", "_")
                    if other_id not in seen and other != name:
                        seen.add(other_id)
                        neighbour = self._client.get_entity(other)
                        if neighbour:
                            neighbours.append({
                                "entity": {
                                    "id": neighbour.id,
                                    "name": neighbour.name,
                                    "type": neighbour.type,
                                    "properties": neighbour.properties,
                                },
                                "relations": self._client.get_relations(
                                    entity_name=other
                                ),
                            })

        return {
            "center": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
                "properties": entity.properties,
            },
            "relations": relations,
            "neighbours": neighbours,
        }

    async def search_entities(
        self, query: str, entity_type: str | None = None
    ) -> list[Entity]:
        """Search entities by name substring, optionally filtered by type."""
        all_entities = self._client.get_all_entities(entity_type)
        q = query.lower()
        return [
            e for e in all_entities if q in e.name.lower() or q in e.id
        ]

    async def get_relation_map(
        self, entity_names: list[str]
    ) -> dict[str, Any]:
        """Get all relations *between* the listed entities.

        Returns a dict with ``"entities"`` and ``"relations"``, where each
        relation has both endpoints in the input list.
        """
        entities = []
        ids = set()
        for name in entity_names:
            entity = self._client.get_entity(name)
            if entity:
                entities.append({
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                })
                ids.add(entity.id)

        all_relations = []
        for name in entity_names:
            for rel in self._client.get_relations(entity_name=name):
                sub_id = rel.get("subject_id", rel.get("subject", "")).lower().replace(" ", "_")
                obj_id = rel.get("object_id", rel.get("object", "")).lower().replace(" ", "_")
                if sub_id in ids and obj_id in ids:
                    all_relations.append(rel)

        # Deduplicate by some unique key
        seen = set()
        unique_relations = []
        for rel in all_relations:
            key = (rel.get("subject", ""), rel.get("predicate", ""), rel.get("object", ""))
            if key not in seen:
                seen.add(key)
                unique_relations.append(rel)

        return {"entities": entities, "relations": unique_relations}

    # ── Stats / Lifecycle ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return storage statistics."""
        return self._client.stats()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._client.close()

    # ── Internal Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _validate_entity_type(entity_type: str) -> None:
        """Raise ``ValidationError`` if the type is not recognised."""
        known = {m.value for m in EntityType}
        known.add("unknown")
        if entity_type not in known:
            raise ValidationError(
                f"Unknown entity type '{entity_type}'. "
                f"Valid types: {sorted(known)}"
            )

    async def _emit_event(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        source: str = "kg_service",
    ) -> None:
        """Publish a system event if an event bus is configured."""
        if self._event_bus is None:
            return
        event = SystemEvent(
            type=event_type,
            source=source,
            payload=payload,
        )
        await self._event_bus.publish(event)
