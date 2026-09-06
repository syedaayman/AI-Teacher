from unittest.mock import AsyncMock, MagicMock
import pytest

from app.schemas.assessment import Misconception, MisconceptionSeverity
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import Concept, DifficultyLevel
from app.schemas.material import DocumentChunk
from app.schemas.session import TeachingStep
from app.services.teaching_content_engine import (
    RawContentPayload,
    TeachingContentEngine,
)


@pytest.fixture
def sample_concept():
    return Concept(
        concept_id="cpt_b_tree_01",
        name="B-Tree Indexing",
        description="Self-balancing search tree optimized for systems that read and write large blocks of memory.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objectives=[
            "Explain B-Tree node branching and balancing",
            "Trace lookup and insertion complexity",
        ],
    )


@pytest.fixture
def mock_gemini():
    client = MagicMock()
    client.generate_structured = AsyncMock()
    return client


# ====================================================================
# Unit Tests for TeachingContentEngine
# ====================================================================

@pytest.mark.asyncio
async def test_01_explanation_generation_structured(sample_concept, mock_gemini):
    """Verify generate_explanation calls LLM with structured schema and maps all pedagogical fields."""
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="Unlocking Fast Lookups with B-Trees",
        content="B-Trees maintain sorted data with logarithmic time lookups by branching widely rather than deeply.",
        visual_description="A tree diagram with node blocks containing keys [10, 20, 30] and child pointer branches.",
        diagram_required=True,
        code_snippet="class BTreeNode:\n    def __init__(self, leaf=False):\n        self.keys = []\n        self.children = []",
        key_takeaways=[
            "Minimizes disk I/O operations",
            "Every leaf is at the exact same depth",
        ],
        analogy="Think of a library catalog where each drawer points to entire sections rather than single books.",
        real_world_application="Standard index data structure for PostgreSQL, SQLite, and MySQL InnoDB.",
        counter_example="Binary search trees create deep paths that cause excessive disk page faults.",
    )

    engine = TeachingContentEngine(client=mock_gemini)
    delivery = await engine.generate_explanation(
        concept=sample_concept,
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.ENGLISH,
        depth="standard",
    )

    assert delivery.step == TeachingStep.EXPLAIN
    assert delivery.concept_id == "cpt_b_tree_01"
    assert delivery.concept_name == "B-Tree Indexing"
    assert delivery.title == "Unlocking Fast Lookups with B-Trees"
    assert "logarithmic time lookups" in delivery.content
    assert delivery.diagram_required is True
    assert delivery.visual_description is not None
    assert "library catalog" in delivery.analogy
    assert "PostgreSQL" in delivery.real_world_application
    assert len(delivery.key_takeaways) == 2

    # Verify prompt was constructed with correct directives
    call_kwargs = mock_gemini.generate_structured.call_args.kwargs
    assert "B-Tree Indexing" in call_kwargs["prompt"]
    assert "Standard Mode (20-minute lesson)" in call_kwargs["system_instruction"]


@pytest.mark.asyncio
async def test_02_demonstration_generation_structured(sample_concept, mock_gemini):
    """Verify generate_demonstration requests a step-by-step applied trace and code example."""
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="Tracing a B-Tree Search and Node Split",
        content="Let's observe what happens when inserting key 25 into a node with max degree 3.",
        visual_description="Step 1: Target leaf full. Step 2: Split median key 20 up to parent.",
        diagram_required=True,
        code_snippet="def split_child(parent, i, full_child):\n    new_node = BTreeNode()\n    parent.children.insert(i + 1, new_node)",
        key_takeaways=["Splits occur from leaves up to the root"],
    )

    engine = TeachingContentEngine(client=mock_gemini)
    delivery = await engine.generate_demonstration(
        concept=sample_concept,
        difficulty=DifficultyLevel.ADVANCED,
        language=SupportedLanguage.ENGLISH,
        depth="deep_dive",
    )

    assert delivery.step == TeachingStep.DEMONSTRATE
    assert delivery.difficulty == DifficultyLevel.ADVANCED
    assert delivery.code_snippet is not None
    assert "split_child" in delivery.code_snippet

    call_kwargs = mock_gemini.generate_structured.call_args.kwargs
    assert "Deep Dive Mode (60-minute lesson)" in call_kwargs["system_instruction"]


@pytest.mark.asyncio
async def test_03_remediation_generation(sample_concept, mock_gemini):
    """Verify generate_remediation specifically focuses on contrasting the misconception with the correct model."""
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="Clarifying B-Tree vs Binary Search Tree Depths",
        content="It is natural to think B-Trees are just binary trees with more memory, but the critical difference is branching factor.",
        visual_description="Side-by-side comparison: Tall skinny BST (height 15) vs short bushy B-Tree (height 3).",
        diagram_required=True,
        counter_example="Assuming height = O(log2 N) for B-Tree wastes memory estimates; it is actually O(log_B N).",
        key_takeaways=["Branching factor B drastically reduces tree height"],
    )

    misc = Misconception(
        misconception_id="msc_tree_01",
        concept_id="cpt_b_tree_01",
        source_question_id="qst_01",
        description="Believes B-Trees have height log2(N) like binary trees",
        evidence="Student calculated height with base 2 logarithm",
        severity=MisconceptionSeverity.MEDIUM,
    )

    engine = TeachingContentEngine(client=mock_gemini)
    delivery = await engine.generate_remediation(
        concept=sample_concept,
        misconception=misc,
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.ENGLISH,
    )

    assert delivery.step == TeachingStep.EXPLAIN
    assert "Clarifying B-Tree" in delivery.title
    assert delivery.diagram_required is True

    call_kwargs = mock_gemini.generate_structured.call_args.kwargs
    assert "Believes B-Trees have height log2(N)" in call_kwargs["prompt"]
    assert "Remediation Strategy" in call_kwargs["system_instruction"]


@pytest.mark.asyncio
async def test_04_multilingual_directives(sample_concept, mock_gemini):
    """Verify language directives are correctly tailored for English, Hindi, and Hinglish."""
    engine = TeachingContentEngine(client=mock_gemini)

    # English
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="English Title", content="English Content"
    )
    await engine.generate_explanation(sample_concept, language=SupportedLanguage.ENGLISH)
    eng_sys = mock_gemini.generate_structured.call_args.kwargs["system_instruction"]
    assert "clear, pedagogical, professional English" in eng_sys

    # Hindi
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="हिंदी शीर्षक", content="हिंदी विवरण"
    )
    await engine.generate_explanation(sample_concept, language=SupportedLanguage.HINDI)
    hin_sys = mock_gemini.generate_structured.call_args.kwargs["system_instruction"]
    assert "Devanagari" in hin_sys

    # Hinglish
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="Hinglish Title", content="Ye concept samajhte hain"
    )
    await engine.generate_explanation(sample_concept, language=SupportedLanguage.HINGLISH)
    hgl_sys = mock_gemini.generate_structured.call_args.kwargs["system_instruction"]
    assert "Hinglish" in hgl_sys


@pytest.mark.asyncio
async def test_05_depth_directives(sample_concept, mock_gemini):
    """Verify depth directives calibrate quick_overview, standard, and deep_dive modes."""
    engine = TeachingContentEngine(client=mock_gemini)
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="Title", content="Content"
    )

    # Quick overview
    await engine.generate_explanation(sample_concept, depth="quick_overview")
    quick_sys = mock_gemini.generate_structured.call_args.kwargs["system_instruction"]
    assert "Quick Overview Mode (5-minute lesson)" in quick_sys

    # Deep dive
    await engine.generate_explanation(sample_concept, depth="deep_dive")
    deep_sys = mock_gemini.generate_structured.call_args.kwargs["system_instruction"]
    assert "Deep Dive Mode (60-minute lesson)" in deep_sys


@pytest.mark.asyncio
async def test_06_material_grounding_in_prompt(sample_concept, mock_gemini):
    """Verify uploaded document chunks are injected into the prompt for grounded teaching."""
    engine = TeachingContentEngine(client=mock_gemini)
    mock_gemini.generate_structured.return_value = RawContentPayload(
        title="Grounded Title", content="Grounded Content"
    )

    chunks = [
        DocumentChunk(
            chunk_id="chk_01",
            material_id="mat_db_internals",
            filename="db_internals.pdf",
            file_type="pdf",
            chunk_index=0,
            text="Chapter 4: B-Trees maximize fanout to minimize disk page fetches per lookup.",
        )
    ]

    await engine.generate_explanation(sample_concept, source_chunks=chunks)
    prompt = mock_gemini.generate_structured.call_args.kwargs["prompt"]
    assert "SOURCE MATERIAL GROUNDING:" in prompt
    assert "Chapter 4: B-Trees maximize fanout" in prompt


@pytest.mark.asyncio
async def test_07_resilient_fallback_on_llm_error(sample_concept, mock_gemini):
    """Verify engine falls back to deterministic delivery if the LLM client raises an exception."""
    mock_gemini.generate_structured.side_effect = RuntimeError("API quota exceeded or network disconnect")

    engine = TeachingContentEngine(client=mock_gemini)

    # Fallback explanation
    delivery = await engine.generate_explanation(
        concept=sample_concept,
        language=SupportedLanguage.HINGLISH,
    )
    assert delivery.step == TeachingStep.EXPLAIN
    assert delivery.language == SupportedLanguage.HINGLISH
    assert "B-Tree Indexing" in delivery.title
    assert delivery.analogy is not None
    assert delivery.diagram_required is True

    # Fallback demonstration
    demo = await engine.generate_demonstration(
        concept=sample_concept,
        language=SupportedLanguage.ENGLISH,
    )
    assert demo.step == TeachingStep.DEMONSTRATE
    assert demo.code_snippet is not None

    # Fallback remediation
    remed = await engine.generate_remediation(
        concept=sample_concept,
        misconception="Believes trees cannot rebalance automatically",
        language=SupportedLanguage.HINDI,
    )
    assert remed.step == TeachingStep.EXPLAIN
    assert remed.language == SupportedLanguage.HINDI
    assert "निवारण" in remed.title
