import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import (
    ConceptCycleError,
    EmptyConceptInputError,
    EmptySyllabusError,
    InvalidConceptError,
    InvalidRelationshipError,
    LessonPlanningError,
)
from app.schemas.lesson import (
    Concept,
    ConceptGraph,
    ConceptRelationship,
    ConceptRelationshipType,
    DifficultyLevel,
    Lesson,
    RawConceptExtractionResponse,
    RawExtractedConcept,
    RawLessonGrouping,
    RawLessonGroupingResponse,
    Syllabus,
)
from app.schemas.material import DocumentChunk, ExtractedDocument, MaterialMetadata
from app.services.concept_service import ConceptService
from app.services.lesson_planner import LessonPlanner


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def mock_chunks():
    """Create sample DocumentChunk objects with deterministic IDs and metadata."""
    return [
        DocumentChunk(
            chunk_id="chk_mat1_0_aaaa1111",
            material_id="mat_algo_101",
            filename="algorithms.pdf",
            file_type="pdf",
            chunk_index=0,
            text="Variables and data types are fundamental memory storage locations in programming.",
            chapter="Chapter 1: Basics",
            section="1.1 Variables",
            page_number=1,
        ),
        DocumentChunk(
            chunk_id="chk_mat1_1_bbbb2222",
            material_id="mat_algo_101",
            filename="algorithms.pdf",
            file_type="pdf",
            chunk_index=1,
            text="Functions allow code modularization, parameter passing, and scope isolation using variables.",
            chapter="Chapter 1: Basics",
            section="1.2 Functions",
            page_number=2,
        ),
        DocumentChunk(
            chunk_id="chk_mat1_2_cccc3333",
            material_id="mat_algo_101",
            filename="algorithms.pdf",
            file_type="pdf",
            chunk_index=2,
            text="Recursion is a technique where a function calls itself to solve smaller subproblems.",
            chapter="Chapter 2: Advanced Techniques",
            section="2.1 Recursion",
            page_number=5,
        ),
        DocumentChunk(
            chunk_id="chk_mat1_3_dddd4444",
            material_id="mat_algo_101",
            filename="algorithms.pdf",
            file_type="pdf",
            chunk_index=3,
            text="Dynamic Programming optimizes recursion by storing overlapping subproblem solutions in a memo table.",
            chapter="Chapter 2: Advanced Techniques",
            section="2.2 Dynamic Programming",
            page_number=8,
        ),
    ]


@pytest.fixture
def mock_extracted_document(mock_chunks):
    """Create sample ExtractedDocument."""
    return ExtractedDocument(
        material_id="mat_algo_101",
        filename="algorithms.pdf",
        file_type="pdf",
        metadata=MaterialMetadata(
            material_id="mat_algo_101",
            filename="algorithms.pdf",
            file_type="pdf",
            total_pages=10,
            total_chunks=4,
        ),
        chunks=mock_chunks,
        raw_text="Full text of algorithms document",
    )


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client with structured response capability."""
    client = MagicMock()
    client.is_configured = True
    client.generate_structured = AsyncMock()
    return client


# ====================================================================
# Test 1 & 2: Concept Schema & Deterministic Concept IDs
# ====================================================================

def test_01_concept_schema_validation():
    """Validate Concept Pydantic model initialization, defaults, and serialization."""
    concept = Concept(
        concept_id="cpt_test12345678",
        name="Binary Search",
        description="Divide-and-conquer search algorithm on sorted arrays.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objectives=[
            "Explain the divide-and-conquer strategy of binary search.",
            "Analyze the O(log n) time complexity.",
        ],
        prerequisite_concept_ids=["cpt_arrays00000000"],
        related_concept_ids=["cpt_linear00000000"],
        source_chunk_ids=["chk_01"],
        source_metadata={"filename": "search.pdf"},
    )
    assert concept.concept_id == "cpt_test12345678"
    assert concept.name == "Binary Search"
    assert concept.difficulty == DifficultyLevel.INTERMEDIATE
    assert len(concept.learning_objectives) == 2
    assert concept.prerequisite_concept_ids == ["cpt_arrays00000000"]
    assert concept.source_chunk_ids == ["chk_01"]


def test_02_deterministic_concept_ids():
    """Ensure identical concept names and materials generate identical SHA-256 IDs."""
    id1 = ConceptService.generate_concept_id("Binary Search", material_id="mat_01")
    id2 = ConceptService.generate_concept_id("  binary search  ", material_id="mat_01")
    id3 = ConceptService.generate_concept_id("Binary Search", material_id="mat_02")
    id4 = ConceptService.generate_concept_id("Linear Search", material_id="mat_01")

    assert id1.startswith("cpt_")
    assert id1 == id2  # Case & whitespace normalized
    assert id1 != id3  # Scoped to material
    assert id1 != id4  # Different name


def test_02b_empty_concept_name_rejected_for_id():
    """Ensure empty concept name raises InvalidConceptError."""
    with pytest.raises(InvalidConceptError):
        ConceptService.generate_concept_id("   ")


# ====================================================================
# Test 3, 4, 5, 6, 7: Concept Extraction, Deduplication, & Traceability
# ====================================================================

@pytest.mark.asyncio
async def test_03_concept_extraction_grounded(mock_chunks, mock_gemini_client):
    """Test grounded concept extraction with mocked Gemini client."""
    mock_gemini_client.generate_structured.return_value = RawConceptExtractionResponse(
        concepts=[
            RawExtractedConcept(
                name="Variables",
                description="Memory locations for holding data values.",
                difficulty=DifficultyLevel.BEGINNER,
                learning_objectives=["Define variable types.", "Apply variables in expressions."],
                prerequisite_concept_names=[],
                related_concept_names=[],
                source_chunk_ids=["chk_mat1_0_aaaa1111"],
            ),
            RawExtractedConcept(
                name="Functions",
                description="Modular reusable blocks of logic.",
                difficulty=DifficultyLevel.BEGINNER,
                learning_objectives=["Explain function signatures.", "Implement functions with parameters."],
                prerequisite_concept_names=["Variables"],
                related_concept_names=[],
                source_chunk_ids=["chk_mat1_1_bbbb2222"],
            ),
            RawExtractedConcept(
                name="Recursion",
                description="Self-referential function execution.",
                difficulty=DifficultyLevel.INTERMEDIATE,
                learning_objectives=["Analyze base cases and recursive steps."],
                prerequisite_concept_names=["Functions"],
                related_concept_names=[],
                source_chunk_ids=["chk_mat1_2_cccc3333"],
            ),
        ]
    )

    service = ConceptService(client=mock_gemini_client)
    concepts = await service.extract_concepts_from_chunks(mock_chunks, material_id="mat_algo_101")

    assert len(concepts) == 3
    var_c = next(c for c in concepts if c.name == "Variables")
    fn_c = next(c for c in concepts if c.name == "Functions")
    rec_c = next(c for c in concepts if c.name == "Recursion")

    # Traceability: Chunk IDs preserved
    assert "chk_mat1_0_aaaa1111" in var_c.source_chunk_ids
    assert "chk_mat1_1_bbbb2222" in fn_c.source_chunk_ids
    assert "chk_mat1_2_cccc3333" in rec_c.source_chunk_ids

    # Prerequisites resolved to deterministic IDs
    assert var_c.concept_id in fn_c.prerequisite_concept_ids
    assert fn_c.concept_id in rec_c.prerequisite_concept_ids


@pytest.mark.asyncio
async def test_04_concept_normalization_and_deduplication(mock_gemini_client):
    """Test duplicate concept merging, objective aggregation, and filler filtering."""
    service = ConceptService(client=mock_gemini_client)
    c1 = Concept(
        concept_id="cpt_var_1234",
        name="Variables",
        description="Variables concept part 1.",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Define variables."],
        prerequisite_concept_ids=[],
        related_concept_ids=[],
        source_chunk_ids=["chk_01"],
        source_metadata={"section": "1.1"},
    )
    c2 = Concept(
        concept_id="cpt_var_1234",  # Same ID (duplicate)
        name="Variables",
        description="Variables concept part 2.",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Apply variables in arithmetic."],
        prerequisite_concept_ids=[],
        related_concept_ids=[],
        source_chunk_ids=["chk_02"],
        source_metadata={"section": "1.2"},
    )

    merged = service.normalize_concepts([c1, c2])
    assert len(merged) == 1
    assert merged[0].concept_id == "cpt_var_1234"
    assert set(merged[0].source_chunk_ids) == {"chk_01", "chk_02"}
    assert len(merged[0].learning_objectives) == 2


@pytest.mark.asyncio
async def test_05_source_chunk_traceability(mock_extracted_document, mock_gemini_client):
    """Test full document extraction preserves material and chunk metadata."""
    mock_gemini_client.generate_structured.return_value = RawConceptExtractionResponse(
        concepts=[
            RawExtractedConcept(
                name="Variables",
                description="Memory locations.",
                difficulty=DifficultyLevel.BEGINNER,
                learning_objectives=["Define variables."],
                source_chunk_ids=["chk_mat1_0_aaaa1111"],
            )
        ]
    )
    service = ConceptService(client=mock_gemini_client)
    concepts = await service.extract_concepts_from_document(mock_extracted_document)

    assert len(concepts) == 1
    assert concepts[0].source_chunk_ids == ["chk_mat1_0_aaaa1111"]
    assert "filenames" in concepts[0].source_metadata
    assert "algorithms.pdf" in concepts[0].source_metadata["filenames"]


# ====================================================================
# Test 8, 9, 10, 11: Concept Relationship & Graph Construction
# ====================================================================

def test_08_concept_relationships_and_graph():
    """Test ConceptRelationship data model and ConceptGraph construction."""
    c1 = Concept(
        concept_id="cpt_c1",
        name="Variables",
        description="Variables",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Define variables."],
        prerequisite_concept_ids=[],
        related_concept_ids=["cpt_c2"],
    )
    c2 = Concept(
        concept_id="cpt_c2",
        name="Data Types",
        description="Data Types",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Identify data types."],
        prerequisite_concept_ids=["cpt_c1"],
        related_concept_ids=["cpt_c1"],
    )

    service = ConceptService()
    graph = service.build_concept_graph([c1, c2])

    assert isinstance(graph, ConceptGraph)
    assert len(graph.concepts) == 2
    assert len(graph.relationships) >= 2

    # Verify prerequisite relationship
    prereq_rels = [
        r for r in graph.relationships
        if r.relationship_type == ConceptRelationshipType.PREREQUISITE
    ]
    assert len(prereq_rels) == 1
    assert prereq_rels[0].source_concept_id == "cpt_c1"
    assert prereq_rels[0].target_concept_id == "cpt_c2"


def test_09_invalid_relationship_rejection():
    """Ensure referencing a non-existent concept ID raises InvalidRelationshipError."""
    c1 = Concept(
        concept_id="cpt_c1",
        name="Variables",
        description="Variables",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Define variables."],
        prerequisite_concept_ids=["cpt_NONEXISTENT"],
    )
    service = ConceptService()
    with pytest.raises(InvalidRelationshipError):
        service.build_concept_graph([c1])


# ====================================================================
# Test 12 & 13: Cycle Detection & Deterministic Topological Sorting
# ====================================================================

def test_12_cycle_detection_direct():
    """Detect direct 2-node cycle (A -> B -> A) and raise ConceptCycleError."""
    c1 = Concept(
        concept_id="cpt_a",
        name="Concept A",
        description="Desc A",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Obj A"],
        prerequisite_concept_ids=["cpt_b"],
    )
    c2 = Concept(
        concept_id="cpt_b",
        name="Concept B",
        description="Desc B",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Obj B"],
        prerequisite_concept_ids=["cpt_a"],
    )
    service = ConceptService()
    with pytest.raises(ConceptCycleError) as exc_info:
        service.build_concept_graph([c1, c2])
    assert "Circular prerequisite dependency" in str(exc_info.value)


def test_12b_cycle_detection_indirect():
    """Detect indirect 3-node cycle (A -> B -> C -> A) and raise ConceptCycleError."""
    c1 = Concept(
        concept_id="cpt_a",
        name="Concept A",
        description="Desc A",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Obj A"],
        prerequisite_concept_ids=["cpt_c"],  # A depends on C
    )
    c2 = Concept(
        concept_id="cpt_b",
        name="Concept B",
        description="Desc B",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Obj B"],
        prerequisite_concept_ids=["cpt_a"],  # B depends on A
    )
    c3 = Concept(
        concept_id="cpt_c",
        name="Concept C",
        description="Desc C",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Obj C"],
        prerequisite_concept_ids=["cpt_b"],  # C depends on B
    )
    service = ConceptService()
    with pytest.raises(ConceptCycleError):
        service.topological_sort([c1, c2, c3])


def test_13_valid_topological_sorting():
    """Verify linear prerequisite chain sorts in exact prerequisite order (A -> B -> C -> D)."""
    # A has no prereq
    ca = Concept(concept_id="cpt_a", name="Variables", description="A", difficulty=DifficultyLevel.BEGINNER, learning_objectives=["Obj A"])
    # B depends on A
    cb = Concept(concept_id="cpt_b", name="Functions", description="B", difficulty=DifficultyLevel.BEGINNER, learning_objectives=["Obj B"], prerequisite_concept_ids=["cpt_a"])
    # C depends on B
    cc = Concept(concept_id="cpt_c", name="Recursion", description="C", difficulty=DifficultyLevel.INTERMEDIATE, learning_objectives=["Obj C"], prerequisite_concept_ids=["cpt_b"])
    # D depends on C
    cd = Concept(concept_id="cpt_d", name="Dynamic Programming", description="D", difficulty=DifficultyLevel.ADVANCED, learning_objectives=["Obj D"], prerequisite_concept_ids=["cpt_c"])

    service = ConceptService()
    # Pass them in scrambled order
    sorted_concepts = service.topological_sort([cd, ca, cc, cb])

    sorted_ids = [c.concept_id for c in sorted_concepts]
    assert sorted_ids == ["cpt_a", "cpt_b", "cpt_c", "cpt_d"]


# ====================================================================
# Test 14, 15: Pedagogical Lesson Grouping & Sequencing
# ====================================================================

@pytest.mark.asyncio
async def test_14_lesson_grouping_heuristic():
    """Verify heuristic grouping bundles concepts into coherent pedagogical units."""
    ca = Concept(concept_id="cpt_a", name="Variables", description="A", difficulty=DifficultyLevel.BEGINNER, learning_objectives=["Obj A"])
    cb = Concept(concept_id="cpt_b", name="Data Types", description="B", difficulty=DifficultyLevel.BEGINNER, learning_objectives=["Obj B"], prerequisite_concept_ids=["cpt_a"])
    cc = Concept(concept_id="cpt_c", name="Functions", description="C", difficulty=DifficultyLevel.INTERMEDIATE, learning_objectives=["Obj C"], prerequisite_concept_ids=["cpt_b"])
    cd = Concept(concept_id="cpt_d", name="Scope", description="D", difficulty=DifficultyLevel.INTERMEDIATE, learning_objectives=["Obj D"], prerequisite_concept_ids=["cpt_c"])

    service = ConceptService()
    graph = service.build_concept_graph([ca, cb, cc, cd])

    # Instantiate planner without LLM key to force deterministic heuristic grouping
    unconfigured_client = MagicMock()
    unconfigured_client.is_configured = False

    planner = LessonPlanner(concept_svc=service, client=unconfigured_client)
    lessons = await planner.group_concepts_into_lessons(
        concepts=[ca, cb, cc, cd],
        concept_graph=graph,
        syllabus_id="syl_test123",
        source_material_ids=["mat_01"],
    )

    assert len(lessons) >= 1
    assert len(lessons) < 4  # Does NOT create 1 lesson per concept
    total_grouped_cids = sum([len(l.concept_ids) for l in lessons])
    assert total_grouped_cids == 4


def test_15_lesson_sequencing():
    """Verify lessons are sequenced topologically and prerequisite_lesson_ids are properly assigned."""
    ca = Concept(concept_id="cpt_a", name="Variables", description="A", difficulty=DifficultyLevel.BEGINNER, learning_objectives=["Obj A"])
    cb = Concept(concept_id="cpt_b", name="Functions", description="B", difficulty=DifficultyLevel.INTERMEDIATE, learning_objectives=["Obj B"], prerequisite_concept_ids=["cpt_a"])

    l1 = Lesson(
        lesson_id="lsn_1",
        title="Lesson 1: Foundations",
        description="Basics",
        concept_ids=["cpt_a"],
        learning_objectives=["Obj A"],
        prerequisite_lesson_ids=[],
        difficulty=DifficultyLevel.BEGINNER,
        estimated_duration_minutes=30,
        sequence_index=0,
    )
    l2 = Lesson(
        lesson_id="lsn_2",
        title="Lesson 2: Modular Programming",
        description="Functions",
        concept_ids=["cpt_b"],
        learning_objectives=["Obj B"],
        prerequisite_lesson_ids=[],
        difficulty=DifficultyLevel.INTERMEDIATE,
        estimated_duration_minutes=30,
        sequence_index=1,
    )

    planner = LessonPlanner()
    # Feed in reverse order
    sequenced = planner.sequence_lessons(lessons=[l2, l1], concepts=[ca, cb], syllabus_id="syl_test")

    assert len(sequenced) == 2
    assert sequenced[0].sequence_index == 0
    assert sequenced[1].sequence_index == 1
    assert sequenced[0].concept_ids == ["cpt_a"]
    assert sequenced[1].concept_ids == ["cpt_b"]
    assert sequenced[0].lesson_id in sequenced[1].prerequisite_lesson_ids


# ====================================================================
# Test 16, 17: Full Syllabus Generation (Material-Grounded)
# ====================================================================

@pytest.mark.asyncio
async def test_16_generate_syllabus_from_material(mock_extracted_document, mock_gemini_client):
    """End-to-end test of material-grounded syllabus generation."""
    mock_gemini_client.generate_structured.side_effect = [
        # 1. Concept extraction
        RawConceptExtractionResponse(
            concepts=[
                RawExtractedConcept(
                    name="Variables",
                    description="Variables storage",
                    difficulty=DifficultyLevel.BEGINNER,
                    learning_objectives=["Define variable scoping."],
                    source_chunk_ids=["chk_mat1_0_aaaa1111"],
                ),
                RawExtractedConcept(
                    name="Functions",
                    description="Reusable functions",
                    difficulty=DifficultyLevel.BEGINNER,
                    learning_objectives=["Apply functions in code."],
                    prerequisite_concept_names=["Variables"],
                    source_chunk_ids=["chk_mat1_1_bbbb2222"],
                ),
            ]
        ),
        # 2. Lesson grouping
        RawLessonGroupingResponse(
            lessons=[
                RawLessonGrouping(
                    title="Introduction to Programming Logic",
                    description="Covers variables and functions.",
                    concept_names=["Variables", "Functions"],
                    estimated_duration_minutes=45,
                )
            ]
        ),
    ]

    service = ConceptService(client=mock_gemini_client)
    planner = LessonPlanner(concept_svc=service, client=mock_gemini_client)

    syllabus = await planner.generate_syllabus_from_material(mock_extracted_document)

    assert isinstance(syllabus, Syllabus)
    assert syllabus.is_grounded is True
    assert syllabus.generation_mode == "material_grounded"
    assert syllabus.source_material_ids == ["mat_algo_101"]
    assert len(syllabus.concepts) == 2
    assert len(syllabus.lessons) == 1
    assert syllabus.lesson_ids == [syllabus.lessons[0].lesson_id]
    assert syllabus.syllabus_id.startswith("syl_")


# ====================================================================
# Test 18: Topic-Only Syllabus Generation
# ====================================================================

@pytest.mark.asyncio
async def test_18_generate_syllabus_from_topic(mock_gemini_client):
    """End-to-end test of topic-only syllabus generation with ungrounded tags."""
    mock_gemini_client.generate_structured.side_effect = [
        RawConceptExtractionResponse(
            concepts=[
                RawExtractedConcept(
                    name="Photosynthesis Basics",
                    description="Overview of light reaction",
                    difficulty=DifficultyLevel.BEGINNER,
                    learning_objectives=["Explain the light-dependent stage."],
                    prerequisite_concept_names=[],
                    source_chunk_ids=[],  # Must be empty in topic_only
                ),
                RawExtractedConcept(
                    name="Calvin Cycle",
                    description="Light independent carbon fixation",
                    difficulty=DifficultyLevel.INTERMEDIATE,
                    learning_objectives=["Trace the stages of the Calvin Cycle."],
                    prerequisite_concept_names=["Photosynthesis Basics"],
                    source_chunk_ids=[],
                ),
            ]
        ),
        RawLessonGroupingResponse(
            lessons=[
                RawLessonGrouping(
                    title="Plant Energetics",
                    description="Covers light reactions and Calvin cycle.",
                    concept_names=["Photosynthesis Basics", "Calvin Cycle"],
                    estimated_duration_minutes=40,
                )
            ]
        ),
    ]

    service = ConceptService(client=mock_gemini_client)
    planner = LessonPlanner(concept_svc=service, client=mock_gemini_client)

    syllabus = await planner.generate_syllabus_from_topic("Photosynthesis")

    assert syllabus.is_grounded is False
    assert syllabus.generation_mode == "topic_only"
    assert syllabus.source_material_ids == []
    for c in syllabus.concepts:
        assert c.source_chunk_ids == []
        assert c.source_metadata == {}


# ====================================================================
# Test 19, 20, 21: Error Handling & Determinism
# ====================================================================

@pytest.mark.asyncio
async def test_19_empty_input_rejections():
    """Ensure empty documents, empty chunk lists, and empty topics raise EmptyConceptInputError."""
    service = ConceptService()
    planner = LessonPlanner(concept_svc=service)

    with pytest.raises(EmptyConceptInputError):
        await service.extract_concepts_from_chunks([])

    with pytest.raises(EmptyConceptInputError):
        await service.extract_concepts_from_topic("   ")

    with pytest.raises(EmptyConceptInputError):
        await planner.generate_syllabus_from_topic("")


def test_21_syllabus_id_determinism():
    """Verify syllabus_id is deterministic and ignores generated_at timestamp."""
    syl_id_1 = LessonPlanner.generate_syllabus_id(
        title="Data Structures",
        concept_ids=["cpt_b", "cpt_a"],  # Unsorted
        mode="material_grounded",
        material_ids=["mat_02", "mat_01"],  # Unsorted
    )
    syl_id_2 = LessonPlanner.generate_syllabus_id(
        title="  data structures  ",
        concept_ids=["cpt_a", "cpt_b"],
        mode="material_grounded",
        material_ids=["mat_01", "mat_02"],
    )
    assert syl_id_1 == syl_id_2
    assert syl_id_1.startswith("syl_")


def test_22_cross_lesson_cycle_detection():
    """Verify ConceptCycleError is raised when grouped lessons form circular dependencies."""
    ca = Concept(concept_id="cpt_a", name="A", description="A", difficulty=DifficultyLevel.BEGINNER, learning_objectives=["Obj A"], prerequisite_concept_ids=["cpt_b"])
    cb = Concept(concept_id="cpt_b", name="B", description="B", difficulty=DifficultyLevel.BEGINNER, learning_objectives=["Obj B"], prerequisite_concept_ids=["cpt_a"])

    l1 = Lesson(
        lesson_id="lsn_1",
        title="Lesson 1",
        description="L1",
        concept_ids=["cpt_a"],
        learning_objectives=["Obj A"],
        prerequisite_lesson_ids=[],
        difficulty=DifficultyLevel.BEGINNER,
        estimated_duration_minutes=30,
        sequence_index=0,
    )
    l2 = Lesson(
        lesson_id="lsn_2",
        title="Lesson 2",
        description="L2",
        concept_ids=["cpt_b"],
        learning_objectives=["Obj B"],
        prerequisite_lesson_ids=[],
        difficulty=DifficultyLevel.BEGINNER,
        estimated_duration_minutes=30,
        sequence_index=1,
    )

    planner = LessonPlanner()
    with pytest.raises(ConceptCycleError):
        planner.sequence_lessons(lessons=[l1, l2], concepts=[ca, cb], syllabus_id="syl_test")


def test_23_difficulty_level_normalization():
    """Verify raw difficulty strings are cleanly coerced to canonical enum values."""
    assert ConceptService._normalize_difficulty("easy") == DifficultyLevel.BEGINNER
    assert ConceptService._normalize_difficulty("medium") == DifficultyLevel.INTERMEDIATE
    assert ConceptService._normalize_difficulty("hard") == DifficultyLevel.ADVANCED
    assert ConceptService._normalize_difficulty("advanced") == DifficultyLevel.ADVANCED
    assert ConceptService._normalize_difficulty(None) == DifficultyLevel.BEGINNER


def test_24_measurable_learning_objectives_action_verbs():
    """Verify fallback measurable action verbs when model returns empty objectives."""
    objs = ConceptService._sanitize_learning_objectives([], "Binary Search")
    assert len(objs) == 2
    assert any("Define" in o for o in objs)
    assert any("Explain" in o for o in objs)


@pytest.mark.asyncio
async def test_25_filler_concepts_filtered_out(mock_chunks, mock_gemini_client):
    """Verify navigation/filler concepts (Table of Contents, Index) are excluded."""
    mock_gemini_client.generate_structured.return_value = RawConceptExtractionResponse(
        concepts=[
            RawExtractedConcept(
                name="Table of Contents",
                description="List of chapters.",
                difficulty=DifficultyLevel.BEGINNER,
                learning_objectives=[],
                source_chunk_ids=["chk_01"],
            ),
            RawExtractedConcept(
                name="Memory Management",
                description="Allocation of heap and stack memory.",
                difficulty=DifficultyLevel.INTERMEDIATE,
                learning_objectives=["Explain stack vs heap memory."],
                source_chunk_ids=["chk_mat1_0_aaaa1111"],
            ),
        ]
    )

    service = ConceptService(client=mock_gemini_client)
    concepts = await service.extract_concepts_from_chunks(mock_chunks, material_id="mat_algo_101")

    assert len(concepts) == 1
    assert concepts[0].name == "Memory Management"
