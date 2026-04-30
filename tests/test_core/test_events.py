"""Tests for event type definitions."""

from uuid import UUID, uuid4

from novelagent.core import EventMetadata, EventType, NarrativeEvent, SystemEvent


class TestEventType:
    """EventType enum values match the design document."""

    def test_values(self) -> None:
        assert EventType.SCENE_STARTED == "SceneStarted"
        assert EventType.NARRATIVE_OUTPUT == "NarrativeOutput"
        assert EventType.BRANCH_CREATED == "BranchCreated"
        assert EventType.MERGE_CONFLICT_DETECTED == "MergeConflictDetected"
        assert EventType.PLAN_STEP_EXECUTED == "PlanStepExecuted"

    def test_all_event_types_have_values(self) -> None:
        """Every enum member has a non-empty string value."""
        for member in EventType:
            assert len(member.value) > 0


class TestEventMetadata:
    """EventMetadata defaults and fields."""

    def test_default_importance(self) -> None:
        meta = EventMetadata()
        assert meta.importance == 0.5

    def test_default_randomness_seed(self) -> None:
        meta = EventMetadata()
        assert meta.randomness_seed == 0.0

    def test_custom_values(self) -> None:
        meta = EventMetadata(importance=0.9, model_used="claude-sonnet-4-6", cost=0.05)
        assert meta.importance == 0.9
        assert meta.model_used == "claude-sonnet-4-6"
        assert meta.cost == 0.05

    def test_timestamp_is_set_on_creation(self) -> None:
        meta = EventMetadata()
        assert meta.timestamp is not None


class TestSystemEvent:
    """SystemEvent creation and field defaults."""

    def test_default_branch_is_main(self) -> None:
        event = SystemEvent(type=EventType.SCENE_STARTED)
        assert event.branch_id == "main"

    def test_auto_generates_uuid(self) -> None:
        event = SystemEvent(type=EventType.NARRATIVE_ADVANCE)
        assert isinstance(event.id, UUID)

    def test_unique_ids(self) -> None:
        e1 = SystemEvent(type=EventType.NARRATIVE_ADVANCE)
        e2 = SystemEvent(type=EventType.NARRATIVE_ADVANCE)
        assert e1.id != e2.id

    def test_type_and_source(self) -> None:
        event = SystemEvent(type=EventType.SCENE_STARTED, source="plot_engine")
        assert event.type == EventType.SCENE_STARTED
        assert event.source == "plot_engine"

    def test_parent_event_id(self) -> None:
        parent_id = uuid4()
        event = SystemEvent(
            type=EventType.NARRATIVE_ADVANCE,
            parent_event_id=parent_id,
        )
        assert event.parent_event_id == parent_id

    def test_payload(self) -> None:
        event = SystemEvent(
            type=EventType.SCENE_STARTED,
            payload={"chapter": 1, "scene": 3},
        )
        assert event.payload == {"chapter": 1, "scene": 3}

    def test_metadata_is_auto_created(self) -> None:
        event = SystemEvent(type=EventType.NARRATIVE_ADVANCE)
        assert event.metadata is not None
        assert isinstance(event.metadata, EventMetadata)

    def test_branch_id(self) -> None:
        event = SystemEvent(type=EventType.NARRATIVE_ADVANCE, branch_id="feature-1")
        assert event.branch_id == "feature-1"


class TestNarrativeEvent:
    """NarrativeEvent creation and field defaults."""

    def test_default_branch_is_main(self) -> None:
        event = NarrativeEvent()
        assert event.branch_id == "main"

    def test_auto_generates_uuid(self) -> None:
        event = NarrativeEvent()
        assert isinstance(event.id, UUID)

    def test_unique_ids(self) -> None:
        e1 = NarrativeEvent()
        e2 = NarrativeEvent()
        assert e1.id != e2.id

    def test_chapter_and_scene(self) -> None:
        event = NarrativeEvent(chapter=1, scene=5)
        assert event.chapter == 1
        assert event.scene == 5

    def test_content(self) -> None:
        event = NarrativeEvent(content="Once upon a time...")
        assert event.content == "Once upon a time..."

    def test_involved_entities(self) -> None:
        event = NarrativeEvent(involved_entities=["hero", "villain"])
        assert event.involved_entities == ["hero", "villain"]

    def test_causal_events(self) -> None:
        eid = uuid4()
        event = NarrativeEvent(causal_events=[eid])
        assert event.causal_events == [eid]
