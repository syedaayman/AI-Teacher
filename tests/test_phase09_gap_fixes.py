from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.exceptions import InvalidSessionStateError, TeacherSessionError
from app.db.repository import LearnerRepository
from app.db.session import Base
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel
from app.schemas.rag import RetrievedChunk
from app.schemas.session import (
    AdvanceStepRequest,
    InstructionalDelivery,
    LessonSessionState,
    SessionStatus,
    StartSessionRequest,
    SubmitAnswerRequest,
    TeachingStep,
)
from app.services.rag_service import RAGService
from app.services.session_service import SessionService
from app.services.teacher_agent import TeacherAgent
from app.services.teaching_content_engine import TeachingContentEngine


@pytest_asyncio.fixture
async def test_db():
    """Isolated in-memory database fixture with pre-seeded learner."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        repo = LearnerRepository(session)
        await repo.create_learner(
            learner_id="learner_gap_01",
            name="Ada Lovelace",
            preferred_language="english",
            preferred_difficulty="intermediate",
        )
        yield session

    await engine.dispose()


@pytest.fixture
def sample_retrieved_chunks():
    """Fixture providing realistic retrieved document chunks with citation metadata."""
    return [
        RetrievedChunk(
            chunk_id="chk_page_12_01",
            material_id="mat_operating_systems_101",
            text="Deadlock occurs when two or more processes are unable to proceed because each is waiting for the other.",
            filename="Modern_Operating_Systems_Ch6.pdf",
            file_type="pdf",
            chunk_index=12,
            chapter="Chapter 6: Deadlocks",
            section="6.2 The Coffman Conditions",
            page_number=142,
            slide_number=None,
            similarity_score=0.92,
            distance=0.16,
            source_metadata={"author": "Tanenbaum", "edition": 4},
        ),
        RetrievedChunk(
            chunk_id="chk_page_12_02",
            material_id="mat_operating_systems_101",
            text="The four conditions required for deadlock: Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait.",
            filename="Modern_Operating_Systems_Ch6.pdf",
            file_type="pdf",
            chunk_index=13,
            chapter="Chapter 6: Deadlocks",
            section="6.2 The Coffman Conditions",
            page_number=143,
            slide_number=None,
            similarity_score=0.88,
            distance=0.24,
            source_metadata={"author": "Tanenbaum", "edition": 4},
        ),
    ]


# ====================================================================
# ISSUE 1: RAG GROUNDING & LIVE TEACHER DELIVERY TESTS
# ====================================================================


@pytest.mark.asyncio
async def test_01_material_based_session_retrieves_rag_chunks(test_db, sample_retrieved_chunks):
    """Verify material-based session queries RAGService with concept and material_id."""
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag.search = AsyncMock(return_value=sample_retrieved_chunks)

    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc, rag_svc=mock_rag)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        material_id="mat_operating_systems_101",
        concept_ids=["deadlock_prevention"],
    )

    resp = await agent.start_teaching_session(req, db_session=test_db)

    # 1. RAG search was queried with the concept and the material_id
    mock_rag.search.assert_called_once()
    call_args = mock_rag.search.call_args
    assert "Deadlock Prevention" in call_args.kwargs["query"] or "deadlock_prevention" in call_args.kwargs["query"]
    assert call_args.kwargs["material_id"] == "mat_operating_systems_101"
    assert resp.delivery is not None


@pytest.mark.asyncio
async def test_02_retrieved_chunks_reach_teaching_content_engine(test_db, sample_retrieved_chunks):
    """Verify retrieved chunks are forwarded directly to TeachingContentEngine."""
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag.search = AsyncMock(return_value=sample_retrieved_chunks)

    mock_content_eng = AsyncMock(spec=TeachingContentEngine)
    mock_content_eng.generate_explanation = AsyncMock(
        return_value=InstructionalDelivery(
            step=TeachingStep.EXPLAIN,
            concept_id="deadlock",
            concept_name="Deadlock",
            title="Deadlock Explanation",
            content="A deadlock is an impasse...",
            sources=[{"chunk_id": "chk_page_12_01", "filename": "Modern_Operating_Systems_Ch6.pdf"}],
        )
    )

    session_svc = SessionService()
    agent = TeacherAgent(
        session_svc=session_svc,
        rag_svc=mock_rag,
        content_eng=mock_content_eng,
    )

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        material_id="mat_operating_systems_101",
        concept_ids=["deadlock"],
    )

    resp = await agent.start_teaching_session(req, db_session=test_db)

    # Verify content engine received the exact source chunks retrieved from RAG
    mock_content_eng.generate_explanation.assert_called_once()
    passed_chunks = mock_content_eng.generate_explanation.call_args.kwargs.get("source_chunks")
    assert passed_chunks is not None
    assert len(passed_chunks) == len(sample_retrieved_chunks)
    assert passed_chunks[0].chunk_id == "chk_page_12_01"
    assert passed_chunks[0].filename == "Modern_Operating_Systems_Ch6.pdf"


@pytest.mark.asyncio
async def test_03_teaching_delivery_contains_source_references(test_db, sample_retrieved_chunks):
    """Verify generated TeachingDelivery.sources contains rich citation and page metadata."""
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag.search = AsyncMock(return_value=sample_retrieved_chunks)

    # Use actual TeachingContentEngine (with fallback offline delivery)
    real_content_eng = TeachingContentEngine(client=None)

    session_svc = SessionService()
    agent = TeacherAgent(
        session_svc=session_svc,
        rag_svc=mock_rag,
        content_eng=real_content_eng,
    )

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        material_id="mat_operating_systems_101",
        concept_ids=["deadlock"],
    )

    resp = await agent.start_teaching_session(req, db_session=test_db)

    assert resp.delivery is not None
    assert len(resp.delivery.sources) == 2

    first_source = resp.delivery.sources[0]
    assert first_source["chunk_id"] == "chk_page_12_01"
    assert first_source["material_id"] == "mat_operating_systems_101"
    assert first_source["filename"] == "Modern_Operating_Systems_Ch6.pdf"
    assert first_source["page_number"] == 142
    assert first_source["chapter"] == "Chapter 6: Deadlocks"
    assert first_source["section"] == "6.2 The Coffman Conditions"
    assert first_source["similarity_score"] == 0.92


@pytest.mark.asyncio
async def test_04_material_id_filtering_is_respected(sample_retrieved_chunks):
    """Verify RAGService search and query_knowledge respect material_id filtering."""
    mock_store = MagicMock()
    mock_store.query_similar.return_value = [
        {
            "chunk_id": "chk_01",
            "distance": 0.1,
            "text": "sample text",
            "metadata": {
                "material_id": "mat_target",
                "filename": "target.pdf",
                "file_type": "pdf",
                "chunk_index": 0,
            },
        }
    ]

    rag = RAGService(store=mock_store, client=None)
    rag._generate_single_embedding = AsyncMock(return_value=[0.1] * 768)

    # Test search with material_id
    results = await rag.search(query="paging", material_id="mat_target")
    assert len(results) == 1
    call_where = mock_store.query_similar.call_args.kwargs.get("where")
    assert call_where == {"material_id": "mat_target"}

    # Test query_knowledge alias
    alias_results = await rag.query_knowledge(query="paging", material_id="mat_target")
    assert len(alias_results) == 1


@pytest.mark.asyncio
async def test_05_topic_only_sessions_do_not_call_rag(test_db):
    """Verify topic-only sessions (no material_id) do NOT make unnecessary RAG queries."""
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag.search = AsyncMock()

    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc, rag_svc=mock_rag)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="QuickSort Algorithm",
        concept_ids=["quicksort_partitioning"],
        material_id=None,  # No material
    )

    resp = await agent.start_teaching_session(req, db_session=test_db)

    # RAG search must NOT have been called
    mock_rag.search.assert_not_called()
    assert resp.delivery is not None
    assert resp.delivery.sources == []

    # Advance step to DEMONSTRATE
    advance_req = AdvanceStepRequest(
        session_id=resp.session_id,
        learner_id="learner_gap_01",
    )
    adv_resp = await agent.advance_step(advance_req, db_session=test_db)
    mock_rag.search.assert_not_called()
    assert adv_resp.delivery is not None
    assert adv_resp.delivery.sources == []


@pytest.mark.asyncio
async def test_06_offline_or_empty_rag_results_safe_handling(test_db):
    """Verify that when no chunks match or RAG returns empty, citations are not fabricated."""
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag.search = AsyncMock(return_value=[])

    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc, rag_svc=mock_rag)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        material_id="mat_sparse_doc",
        concept_ids=["rare_concept"],
    )

    resp = await agent.start_teaching_session(req, db_session=test_db)
    mock_rag.search.assert_called_once()
    assert resp.delivery is not None
    assert resp.delivery.sources == []


# ====================================================================
# ISSUE 2: SESSION PERSISTENCE & ACTIVE RECOVERY TESTS
# ====================================================================


@pytest.mark.asyncio
async def test_07_active_session_state_persisted_in_db(test_db):
    """Verify complete LessonSessionState information is persisted in session_logs."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Operating Systems",
        concept_ids=["processes", "threads", "deadlocks"],
        available_time_minutes=45,
        desired_depth="deep_dive",
        preferred_difficulty=DifficultyLevel.ADVANCED,
        preferred_language=SupportedLanguage.ENGLISH,
    )

    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Verify persistent DB record
    repo = LearnerRepository(test_db)
    sess_log = await repo.get_session_log(sid)
    assert sess_log is not None
    assert sess_log.id == sid
    assert sess_log.learner_id == "learner_gap_01"
    assert sess_log.status == "active"
    assert sess_log.current_difficulty == "advanced"
    assert sess_log.language == "english"

    meta = sess_log.session_metadata
    assert meta is not None
    assert meta["session_id"] == sid
    assert meta["concepts"] == ["processes", "threads", "deadlocks"]
    assert meta["current_concept_index"] == 0
    assert meta["time_budget_minutes"] == 45
    assert meta["desired_depth"] == "deep_dive"


@pytest.mark.asyncio
async def test_08_teacher_agent_reconstructs_session_from_db_when_cache_evicted(test_db):
    """Verify TeacherAgent can recover LessonSessionState from DB after cache wipe."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Database Indexing",
        concept_ids=["b_trees", "hash_indexes"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Confirm in cache
    assert sid in agent.active_sessions

    # Simulate process restart / memory eviction
    agent.active_sessions.clear()
    assert sid not in agent.active_sessions

    # Recover session via TeacherAgent
    recovered = await agent.get_or_restore_session(sid, db_session=test_db)
    assert recovered is not None
    assert recovered.session_id == sid
    assert recovered.topic == "Database Indexing"
    assert recovered.concepts == ["b_trees", "hash_indexes"]
    assert recovered.current_concept_index == 0

    # Confirm it was placed back into the active sessions cache
    assert sid in agent.active_sessions


@pytest.mark.asyncio
async def test_09_recovered_session_preserves_concept_and_language(test_db):
    """Verify concept position and multilingual settings survive cache loss."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Graph Algorithms",
        concept_ids=["bfs", "dfs", "dijkstra"],
        preferred_language=SupportedLanguage.ENGLISH,
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Switch language to Hindi mid-session
    await agent.switch_session_language(sid, SupportedLanguage.HINDI, db_session=test_db)

    # Advance state to concept index 1 (DFS)
    state = agent.active_sessions[sid]
    state.current_concept_index = 1
    await session_svc.save_session(state, db_session=test_db)

    # Evict cache
    agent.active_sessions.clear()

    # Recover
    recovered = await agent.get_or_restore_session(sid, db_session=test_db)
    assert recovered.current_concept_index == 1
    assert recovered.current_concept_id == "dfs"
    assert recovered.language == SupportedLanguage.HINDI


@pytest.mark.asyncio
async def test_10_recovered_session_preserves_remediation_and_history(test_db):
    """Verify remediation counts and step history are preserved across recovery."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Sorting",
        concept_ids=["merge_sort"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Add remediation state & history
    state = agent.active_sessions[sid]
    state.remediation_attempts["merge_sort"] = 2
    state.history.append({"step": "remediation_1", "notes": "divide step confusion"})
    await session_svc.save_session(state, db_session=test_db)

    # Evict cache
    agent.active_sessions.clear()

    # Recover
    recovered = await agent.get_or_restore_session(sid, db_session=test_db)
    assert recovered.remediation_attempts.get("merge_sort") == 2
    assert len(recovered.history) == 1
    assert recovered.history[0]["step"] == "remediation_1"


@pytest.mark.asyncio
async def test_11_recovered_session_can_continue_teaching(test_db):
    """Verify an evicted session can directly receive advance_step and continue the loop."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Networking",
        concept_ids=["tcp_handshake"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Evict from active cache
    agent.active_sessions.clear()
    assert sid not in agent.active_sessions

    # Direct advance_step call on evicted session
    advance_req = AdvanceStepRequest(
        session_id=sid,
        learner_id="learner_gap_01",
    )
    adv_resp = await agent.advance_step(advance_req, db_session=test_db)

    # The session should have recovered automatically and transitioned to DEMONSTRATE
    assert adv_resp.session_id == sid
    assert adv_resp.current_step == TeachingStep.DEMONSTRATE
    assert adv_resp.delivery is not None
    assert sid in agent.active_sessions


@pytest.mark.asyncio
async def test_12_completed_sessions_not_restored_as_active_sessions(test_db):
    """Verify completed sessions cannot be restored as active sessions."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Data Structures",
        concept_ids=["array"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Conclude the session
    await session_svc.end_session(sid, SessionStatus.COMPLETED, db_session=test_db)

    # Evict cache
    agent.active_sessions.clear()

    # Fetching with get_active_session must raise InvalidSessionStateError
    with pytest.raises(InvalidSessionStateError) as exc_info:
        await agent.get_active_session(sid, db_session=test_db)
    assert "already completed" in str(exc_info.value)

    # Calling advance_step on completed session returns completion response without changing state
    adv_resp = await agent.advance_step(
        AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"),
        db_session=test_db,
    )
    assert adv_resp.status == SessionStatus.COMPLETED
    assert adv_resp.current_step == TeachingStep.COMPLETE


@pytest.mark.asyncio
async def test_13_live_submit_answer_adaptation(test_db):
    """Verify live submit_answer calls decide_next_action on AdaptiveEngine without AttributeError."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Physics Mechanics",
        concept_ids=["inertia_cpt", "momentum_cpt"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # 1. Advance to DEMONSTRATE
    adv1 = await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    assert adv1.current_step == TeachingStep.DEMONSTRATE

    # 2. Advance to QUESTION
    adv2 = await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    assert adv2.current_step == TeachingStep.QUESTION
    assert adv2.question is not None
    q = adv2.question

    # 3. Submit correct answer
    sub_req = SubmitAnswerRequest(
        session_id=sid,
        learner_id="learner_gap_01",
        question_id=q.question_id,
        answer_text=q.correct_answer,
        reasoning="Inertia resists acceleration unless a net force acts.",
    )
    ans_resp = await agent.submit_answer(sub_req, db_session=test_db)

    # Must not raise AttributeError
    assert ans_resp.evaluation is not None
    assert ans_resp.adaptation is not None
    assert ans_resp.adaptation.action is not None
    # Correct answer advances concept or increases difficulty
    assert ans_resp.evaluation.score >= 0.7


@pytest.mark.asyncio
async def test_14_live_submit_answer_incorrect_remediation_path(test_db):
    """TEST 2: Verify incorrect answer triggers retry/remediation adaptation without crashing."""
    from app.schemas.adaptive import AdaptationAction
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Newtonian Physics",
        concept_ids=["newton_first_law", "newton_second_law"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Advance to question
    await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    adv_q = await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    q = adv_q.question

    # Submit incorrect answer
    sub_req = SubmitAnswerRequest(
        session_id=sid,
        learner_id="learner_gap_01",
        question_id=q.question_id,
        answer_text="Objects stop moving on their own because all motion naturally fades away.",
        reasoning="Motion requires constant active pushing.",
    )
    ans_resp = await agent.submit_answer(sub_req, db_session=test_db)

    assert ans_resp.evaluation is not None
    assert ans_resp.evaluation.score <= 0.6
    assert ans_resp.adaptation is not None
    # Appropriate recovery action selected by AdaptiveEngine
    assert ans_resp.adaptation.action in [
        AdaptationAction.REMEDIATE_MISCONCEPTION,
        AdaptationAction.RETEACH_CONCEPT,
        AdaptationAction.RETRY_QUESTION,
        AdaptationAction.DECREASE_DIFFICULTY,
    ]
    # Session remains active and ready to continue
    assert ans_resp.status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_15_live_submit_answer_misconception_remediation(test_db):
    """TEST 3: Verify diagnosed misconception triggers remediation explanation path."""
    from app.schemas.adaptive import AdaptationAction
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Gravitational Physics",
        concept_ids=["free_fall", "terminal_velocity"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Advance to question
    await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    adv_q = await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    q = adv_q.question

    # Submit classic gravity misconception: heavier objects fall faster
    sub_req = SubmitAnswerRequest(
        session_id=sid,
        learner_id="learner_gap_01",
        question_id=q.question_id,
        answer_text="Heavier objects fall faster because gravity pulls more strongly on heavier objects.",
        reasoning="More weight causes more rapid falling.",
    )
    ans_resp = await agent.submit_answer(sub_req, db_session=test_db)

    assert ans_resp.evaluation is not None
    assert ans_resp.adaptation is not None
    # Adaptive decision generated
    assert ans_resp.adaptation.action in [
        AdaptationAction.REMEDIATE_MISCONCEPTION,
        AdaptationAction.RETEACH_CONCEPT,
        AdaptationAction.RETRY_QUESTION,
    ]
    # Either remediation delivery or retry question is provided to student
    assert ans_resp.delivery is not None or ans_resp.question is not None


@pytest.mark.asyncio
async def test_16_live_submit_answer_session_persistence(test_db):
    """TEST 4: Verify evaluation, mastery, and adaptive decisions persist to SQLite and survive cache loss."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Thermodynamics",
        concept_ids=["heat_transfer", "entropy"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    adv_q = await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    q = adv_q.question

    sub_req = SubmitAnswerRequest(
        session_id=sid,
        learner_id="learner_gap_01",
        question_id=q.question_id,
        answer_text=q.correct_answer,
    )
    await agent.submit_answer(sub_req, db_session=test_db)

    # Evict cache completely
    agent.active_sessions.clear()

    # Retrieve session from DB
    recovered = await agent.get_or_restore_session(sid, db_session=test_db)
    assert recovered is not None
    assert recovered.session_id == sid
    assert recovered.last_evaluation is not None
    assert recovered.last_adaptation is not None
    assert recovered.last_student_answer is not None


@pytest.mark.asyncio
async def test_17_live_submit_answer_invalid_submission_graceful_error(test_db):
    """TEST 5: Verify mismatched or invalid question ID raises controlled error without server crash."""
    session_svc = SessionService()
    agent = TeacherAgent(session_svc=session_svc)

    req = StartSessionRequest(
        learner_id="learner_gap_01",
        topic="Organic Chemistry",
        concept_ids=["alkanes"],
    )
    resp = await agent.start_teaching_session(req, db_session=test_db)
    sid = resp.session_id

    # Advance to question
    await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)
    await agent.advance_step(AdvanceStepRequest(session_id=sid, learner_id="learner_gap_01"), db_session=test_db)

    # Submit with mismatched question_id
    bad_req = SubmitAnswerRequest(
        session_id=sid,
        learner_id="learner_gap_01",
        question_id="qst_fake_nonexistent",
        answer_text="Some random answer",
    )
    with pytest.raises(TeacherSessionError) as exc_info:
        await agent.submit_answer(bad_req, db_session=test_db)
    assert "does not match the active session question" in str(exc_info.value)

    # Session is not corrupted and remains recoverable
    recovered = await agent.get_or_restore_session(sid, db_session=test_db)
    assert recovered.status == SessionStatus.ACTIVE

