"""Event type definitions for the NovelAgent event-driven architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class EventType(StrEnum):
    """Standard event types used across the system."""

    SCENE_STARTED = "SceneStarted"
    SCENE_ENDED = "SceneEnded"
    NARRATIVE_ADVANCE = "NarrativeAdvance"
    NARRATIVE_OUTPUT = "NarrativeOutput"
    CHARACTER_STATE_CHANGED = "CharacterStateChanged"
    RELATION_CHANGED = "RelationChanged"
    BRAINSTORM_REQUESTED = "BrainstormRequested"
    BRAINSTORM_CANDIDATES = "BrainstormCandidates"
    CONSISTENCY_RESULT = "ConsistencyResult"
    USER_SELECTION = "UserSelection"
    BRANCH_CREATED = "BranchCreated"
    BRANCH_MERGED = "BranchMerged"
    MERGE_CONFLICT_DETECTED = "MergeConflictDetected"
    MERGE_CONFLICT_RESOLVED = "MergeConflictResolved"
    KG_QUERY_REQUESTED = "KGQueryRequested"
    KG_QUERY_RESULT = "KGQueryResult"
    MEMORY_TIER_CHANGED = "MemoryTierChanged"
    CHAPTER_PLANNING = "ChapterPlanning"
    NARRATIVE_INTENT = "NarrativeIntent"
    PLAN_STEP_EXECUTED = "PlanStepExecuted"


@dataclass
class EventMetadata:
    """Metadata attached to every system event."""

    timestamp: datetime = field(default_factory=datetime.now)
    randomness_seed: float = 0.0
    importance: float = 0.5
    model_used: str = ""
    cost: float = 0.0


@dataclass
class SystemEvent:
    """A system-level event representing an action or state change."""

    id: UUID = field(default_factory=uuid4)
    type: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    branch_id: str = "main"
    parent_event_id: UUID | None = None
    metadata: EventMetadata = field(default_factory=EventMetadata)


@dataclass
class NarrativeEvent:
    """A narrative text event representing story output."""

    id: UUID = field(default_factory=uuid4)
    type: str = EventType.NARRATIVE_OUTPUT
    chapter: int = 0
    scene: int = 0
    content: str = ""
    involved_entities: list[str] = field(default_factory=list)
    causal_events: list[UUID] = field(default_factory=list)
    branch_id: str = "main"
    timestamp: datetime = field(default_factory=datetime.now)
