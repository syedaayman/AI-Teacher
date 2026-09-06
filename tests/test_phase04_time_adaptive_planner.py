import pytest

from app.core.exceptions import EmptyConceptInputError, EmptySyllabusError
from app.schemas.lesson import (
    Concept,
    ConceptGraph,
    ConceptRelationship,
    ConceptRelationshipType,
    DifficultyLevel,
)
from app.services.time_adaptive_planner import TimeAdaptivePlanner


@pytest.fixture
def sample_concept_graph():
    """A 6-concept DAG representing Database Storage Internals:
    cpt_disk_io (Beginner, root)
      -> cpt_page_buffer (Intermediate)
          -> cpt_b_trees (Intermediate)
              -> cpt_lsm_trees (Advanced)
      -> cpt_wal (Intermediate)
          -> cpt_crash_recovery (Advanced)
    """
    c1 = Concept(
        concept_id="cpt_disk_io",
        name="Disk I/O Fundamentals",
        description="Block storage, rotational latency, and page transfer mechanisms.",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Understand page transfer costs"],
    )
    c2 = Concept(
        concept_id="cpt_page_buffer",
        name="Buffer Pool Management",
        description="In-memory frame caching, LRU, and dirty page flushing.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        prerequisite_concept_ids=["cpt_disk_io"],
        learning_objectives=["Explain cache replacement policies"],
    )
    c3 = Concept(
        concept_id="cpt_b_trees",
        name="B-Tree Page Indexing",
        description="Multi-way search tree structured for disk blocks.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        prerequisite_concept_ids=["cpt_page_buffer"],
        learning_objectives=["Calculate fanout and search depth"],
    )
    c4 = Concept(
        concept_id="cpt_wal",
        name="Write-Ahead Logging",
        description="Append-only sequential logging for ACID durability.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        prerequisite_concept_ids=["cpt_disk_io"],
        learning_objectives=["Describe redo/undo invariants"],
    )
    c5 = Concept(
        concept_id="cpt_crash_recovery",
        name="ARIES Crash Recovery",
        description="Analysis, Redo, and Undo passes recovering consistent state.",
        difficulty=DifficultyLevel.ADVANCED,
        prerequisite_concept_ids=["cpt_wal"],
        learning_objectives=["Trace ARIES recovery algorithm"],
    )
    c6 = Concept(
        concept_id="cpt_lsm_trees",
        name="LSM-Trees & Compaction",
        description="Log-structured merge trees for write-heavy workloads.",
        difficulty=DifficultyLevel.ADVANCED,
        prerequisite_concept_ids=["cpt_b_trees"],
        learning_objectives=["Compare B-Tree vs LSM write amplification"],
    )

    concepts = [c1, c2, c3, c4, c5, c6]
    relationships = [
        ConceptRelationship(source_concept_id="cpt_disk_io", target_concept_id="cpt_page_buffer"),
        ConceptRelationship(source_concept_id="cpt_page_buffer", target_concept_id="cpt_b_trees"),
        ConceptRelationship(source_concept_id="cpt_b_trees", target_concept_id="cpt_lsm_trees"),
        ConceptRelationship(source_concept_id="cpt_disk_io", target_concept_id="cpt_wal"),
        ConceptRelationship(source_concept_id="cpt_wal", target_concept_id="cpt_crash_recovery"),
    ]

    return ConceptGraph(concepts=concepts, relationships=relationships)


# ====================================================================
# Unit Tests for TimeAdaptivePlanner
# ====================================================================

def test_01_quick_overview_5min_pruning(sample_concept_graph):
    """Verify 5-minute quick overview selects 1-2 foundational root concepts."""
    planner = TimeAdaptivePlanner()

    pruned = planner.prune_and_prioritize_concepts(
        concept_graph=sample_concept_graph,
        available_time_minutes=5,
        desired_depth="quick_overview",
    )

    assert 1 <= len(pruned) <= 2
    # The first concept must be the root foundational concept (cpt_disk_io)
    assert pruned[0].concept_id == "cpt_disk_io"


def test_02_standard_20min_pruning(sample_concept_graph):
    """Verify 20-minute standard lesson selects 3 to 5 core concepts with topological ordering."""
    planner = TimeAdaptivePlanner()

    pruned = planner.prune_and_prioritize_concepts(
        concept_graph=sample_concept_graph,
        available_time_minutes=20,
        desired_depth="standard",
    )

    assert 3 <= len(pruned) <= 5
    # Root must precede all dependents
    pruned_ids = [c.concept_id for c in pruned]
    assert "cpt_disk_io" in pruned_ids
    assert pruned_ids.index("cpt_disk_io") == 0


def test_03_deep_dive_60min_retention(sample_concept_graph):
    """Verify 60-minute deep dive retains all reachable concepts in the graph."""
    planner = TimeAdaptivePlanner()

    pruned = planner.prune_and_prioritize_concepts(
        concept_graph=sample_concept_graph,
        available_time_minutes=60,
        desired_depth="deep_dive",
    )

    assert len(pruned) == 6
    pruned_ids = [c.concept_id for c in pruned]
    # Check topological order: prerequisite must always appear before dependent
    assert pruned_ids.index("cpt_disk_io") < pruned_ids.index("cpt_page_buffer")
    assert pruned_ids.index("cpt_page_buffer") < pruned_ids.index("cpt_b_trees")
    assert pruned_ids.index("cpt_b_trees") < pruned_ids.index("cpt_lsm_trees")
    assert pruned_ids.index("cpt_disk_io") < pruned_ids.index("cpt_wal")
    assert pruned_ids.index("cpt_wal") < pruned_ids.index("cpt_crash_recovery")


def test_04_prerequisite_closure_guarantee(sample_concept_graph):
    """Verify prerequisite closure: If a concept is selected, all its prerequisites are included."""
    planner = TimeAdaptivePlanner()

    # Even with tight time, if a concept like cpt_b_trees were to be included,
    # its prerequisites (cpt_page_buffer, cpt_disk_io) MUST be included
    for minutes in [5, 10, 15, 20, 30, 45, 60]:
        pruned = planner.prune_and_prioritize_concepts(sample_concept_graph, minutes)
        pruned_ids = set(c.concept_id for c in pruned)

        for c in pruned:
            for pid in c.prerequisite_concept_ids:
                assert pid in pruned_ids, f"Prerequisite {pid} missing for concept {c.concept_id} at {minutes} min!"


def test_05_time_budgeted_syllabus_creation(sample_concept_graph):
    """Verify syllabus synthesis produces lessons with total duration conforming to the time budget."""
    planner = TimeAdaptivePlanner()

    # 5-minute syllabus
    syl_5 = planner.create_time_budgeted_syllabus(
        concept_graph=sample_concept_graph,
        title="Quick Disk Intro",
        available_time_minutes=5,
        desired_depth="quick_overview",
    )
    assert syl_5.syllabus_id.startswith("syl_")
    assert len(syl_5.lessons) == 1
    assert syl_5.lessons[0].estimated_duration_minutes == 5

    # 20-minute syllabus
    syl_20 = planner.create_time_budgeted_syllabus(
        concept_graph=sample_concept_graph,
        title="Standard Storage",
        available_time_minutes=20,
        desired_depth="standard",
    )
    assert 1 <= len(syl_20.lessons) <= 2
    total_dur_20 = sum(l.estimated_duration_minutes for l in syl_20.lessons)
    assert total_dur_20 == 20

    # 60-minute syllabus
    syl_60 = planner.create_time_budgeted_syllabus(
        concept_graph=sample_concept_graph,
        title="Deep Storage Architecture",
        available_time_minutes=60,
        desired_depth="deep_dive",
    )
    assert len(syl_60.lessons) >= 2
    total_dur_60 = sum(l.estimated_duration_minutes for l in syl_60.lessons)
    assert total_dur_60 == 60


def test_06_concept_time_slices():
    """Verify calculate_concept_time_slices allocates time evenly without loss of minutes."""
    planner = TimeAdaptivePlanner()

    slices_20 = planner.calculate_concept_time_slices(["c1", "c2", "c3"], 20)
    assert sum(slices_20.values()) == 20
    assert slices_20["c1"] >= 6
    assert slices_20["c2"] >= 6
    assert slices_20["c3"] >= 6

    slices_5 = planner.calculate_concept_time_slices(["c1"], 5)
    assert slices_5["c1"] == 5


def test_07_pacing_adaptation():
    """Verify adapt_pacing accurately detects when learner is behind, on track, or ahead."""
    planner = TimeAdaptivePlanner()

    # Behind schedule: 4 minutes remaining for 3 concepts -> 1.33 min/concept < 3.0
    behind = planner.adapt_pacing(remaining_time_minutes=4, remaining_concepts_count=3)
    assert behind["status"] == "behind_schedule"
    assert behind["recommended_action"] == "condense_explanations"
    assert behind["depth_adjustment"] == "quick_overview"

    # Ahead of schedule: 45 minutes remaining for 2 concepts -> 22.5 min/concept > 12.0
    ahead = planner.adapt_pacing(remaining_time_minutes=45, remaining_concepts_count=2)
    assert ahead["status"] == "ahead_of_schedule"
    assert ahead["recommended_action"] == "add_extension_challenge"
    assert ahead["depth_adjustment"] == "deep_dive"

    # On track: 15 minutes remaining for 2 concepts -> 7.5 min/concept
    on_track = planner.adapt_pacing(remaining_time_minutes=15, remaining_concepts_count=2)
    assert on_track["status"] == "on_track"
    assert on_track["recommended_action"] == "continue_standard"


def test_08_empty_input_guard():
    """Verify empty concept graphs raise appropriate domain exceptions."""
    planner = TimeAdaptivePlanner()

    empty_graph = ConceptGraph(concepts=[], relationships=[])
    with pytest.raises(EmptyConceptInputError):
        planner.prune_and_prioritize_concepts(empty_graph, 20)

    with pytest.raises(EmptySyllabusError):
        planner.create_time_budgeted_syllabus(empty_graph, "Title", 20)


def test_09_seven_day_plan(sample_concept_graph):
    """Verify generate_seven_day_plan produces a structured 7-day schedule with spaced revision."""
    planner = TimeAdaptivePlanner()

    plan = planner.generate_seven_day_plan(
        concept_graph=sample_concept_graph,
        topic="Database Storage Internals",
        daily_minutes=30,
    )

    assert plan["topic"] == "Database Storage Internals"
    assert plan["daily_minutes"] == 30
    assert len(plan["days"]) == 7

    # Day 1 should have foundation concepts
    day1 = plan["days"][0]
    assert day1["day"] == 1
    assert len(day1["concepts"]) > 0
    assert day1["available_time_minutes"] == 30

    # Day 3 and Day 5 should have spaced revision requirements
    day3 = plan["days"][2]
    assert day3["day"] == 3
    assert len(day3["revision_requirements"]) > 0

    day7 = plan["days"][6]
    assert day7["day"] == 7
    assert "Assessment" in day7["title"]

