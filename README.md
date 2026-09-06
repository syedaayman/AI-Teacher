# AI Brain (Member 1 Backend)

The **AI Brain** is the backend intelligence, reasoning, memory, evaluation, and knowledge engine of the AI Teacher system. It exposes structured APIs consumed by **Member 2 (AI Classroom)**.

> **Current Status**: **Phase 1 (Foundation)**, **Phase 2 (Material Processing)**, **Phase 3 (RAG / Knowledge Grounding)**, **Phase 4 (Lesson Planning & Syllabus)**, **Phase 5 (Question Generation & Evaluation)**, **Phase 6 (Adaptive Learning Engine)** & **Phase 7 (Learner Profile System)** implemented.
> 
> *Note: Phase 7 provides structured current learner profile state and preferences. Historical learning memory, teacher conversational dialogue, TTS/audio, and avatar animation belong to subsequent phases.*

---

## Phase Overview

### Phase 1 — Foundation
- FastAPI async web application framework.
- Centralized environment configuration via Pydantic Settings.
- Isolated Google GenAI client wrapper (`gemini-2.5-flash` / `gemini-embedding-001`).
- Async database session infrastructure with SQLAlchemy 2.x and `aiosqlite`.
- Common Pydantic response and error schemas.
- Health check endpoints (`/health` and `/api/v1/health`).

### Phase 2 — Material Processing
- **Document Processing Pipeline**: End-to-end ingestion and normalization for PDF, DOCX, PPTX, and TXT documents.
- **Modular Extractors**: PDF (`pypdf`), DOCX (`python-docx`), PPTX (`python-pptx`), and TXT with metadata preservation.
- **Deterministic Text Cleaning**: Normalizes line breaks, whitespace, and empty lines without destroying formulas or code.
- **Hierarchical Chunking**: Respects Chapter → Section → Page/Slide → Paragraph → Sentence boundaries.
- **Deterministic Chunk Identifiers**: SHA-256 hash-based deterministic IDs (`chk_<mat_id>_<index>_<hash>`).

### Phase 3 — RAG / Knowledge Grounding
- **Vector Store Persistence**: Persistent local ChromaDB storage with sanitized metadata serialization.
- **Embedding Generation**: Vector embeddings powered by `GEMINI_EMBEDDING_MODEL` (`gemini-embedding-001`).
- **Semantic Retrieval**: Cosine distance similarity search returning ranked `RetrievedChunk` instances.
- **Grounded Context Construction**: Structured context compiler with source reference tags.

### Phase 4 — Lesson Planning, Concept Graph & Syllabus Generation
- **Pedagogical Concept Graph**: Models concepts, measurable learning objectives, and typed relationships (`prerequisite`, `related`).
- **Graph Validation & Cycle Detection**: DFS-powered prerequisite cycle detection (`ConceptCycleError`) and deterministic topological sorting.
- **Syllabus & Lesson Sequencing**: Pedagogical lesson grouping and sequencing for material-grounded and topic-only modes.

### Phase 5 — Question Generation, Answer Evaluation & Misconception Detection
- **Question Generation**: Generates MCQ, Short Answer, Conceptual, and Application questions from Phase 4 concepts with deterministic SHA-256 IDs.
- **Answer Evaluation**: Deterministic exact matching for MCQs and semantic LLM evaluation for open-ended answers with normalized scoring (0.0–1.0).
- **Misconception Detection**: Diagnoses genuine conceptual and prerequisite flaws, distinguishing them from typos or slips.

### Phase 6 — Adaptive Learning Engine
- **Mastery Calculation**: Pure Python, deterministic weighted formula ($0.6 \times \text{previous} + 0.4 \times \text{current}$) and 5-tier mastery levels.
- **Prioritized Adaptation**: 6-tier hierarchy evaluating prerequisite misconceptions, conceptual misconceptions, repeated failures, low mastery, partial understanding, and advancement.
- **Deterministic Decision IDs**: SHA-256 hashes (`adt_<hash[:16]>`) with explainable evidence trails.

### Phase 7 — Learner Profile System
- **Purpose**: Structured representation of the learner's current identity, instructional preferences, learning goals, concept mastery, strengths, weak areas, and lesson progress.
- **Architecture**:
  ```text
  Phase 6 ConceptMastery
              │
              ▼
  ┌────────────────────────────────────────────────────────┐
  │         LearnerProfileService (Deterministic, No LLM)  │
  │  - Profiles: learner_id, name, preferred_language,     │
  │    preferred_difficulty, learning_goal                 │
  │  - Concept Masteries: Dict[concept_id, ConceptMastery] │
  │  - Overall Mastery: Deterministic mean of masteries    │
  │  - Strengths: PROFICIENT / MASTERED concepts           │
  │  - Weak Areas: NOT_STARTED / EMERGING concepts         │
  │  - Active Concepts: EMERGING / DEVELOPING concepts     │
  │  - Lesson Progress: completed_lessons (deduped list)   │
  │  - Running Average: incremental average score          │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │         LearnerProfile                                 │
  │  - Consumed by Lesson Planner, Adaptive Engine,        │
  │    and future Teacher Agent / Multilingual engines     │
  └────────────────────────────────────────────────────────┘
  ```
- **Architectural Separation**:
  - **LearnerProfile**: Current structured state, preferences, and aggregate mastery metrics.
  - **LessonSessionState**: Transient live session orchestrator state (`current_difficulty`, `current_step`).
  - **Learning Memory (Phase 8+)**: Persistent historical event logs, past conversation trajectories, and spaced repetition memory.
- **Languages Supported**: `english`, `hindi`, `hinglish`.
- **Deterministic Operations**: Zero LLM calls for profile creation, preference updates, running averages, or strength/weakness classifications.

---

## Limitations & Phase Boundaries

- **Scanned PDFs & OCR**: OCR is **not** implemented. Scanned PDFs without embedded text raise `EmptyDocumentError`.
- **Teacher Dialogue & Avatar Execution**: Phase 6 selects adaptive pedagogical actions. Conversational teacher dialogue, spoken text generation, TTS, avatar animations, and classroom WebSockets belong to subsequent phases.

---

## Requirements

- Python 3.11+
- Virtual environment (`venv` or `conda`)

---

## Installation

1. Clone or open the repository.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Environment Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Configure your variables in `.env`:
```ini
APP_ENV=development
DEBUG=true

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

DATABASE_URL=sqlite+aiosqlite:///./ai_brain.db
CHROMA_PERSIST_DIRECTORY=./chroma_data
```

---

## Running the Application

### Prerequisites
- Python 3.10+
- Node.js 18+ (with npm)
- Google Gemini API Key (from [Google AI Studio](https://aistudio.google.com/apikey))

### 1. Start the FastAPI Backend
```bash
# Activate virtual environment:
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

uvicorn main:app --reload --host 0.0.0.0 --port 8001
```
- API Endpoint: `http://localhost:8001`
- Swagger Documentation: `http://localhost:8001/docs`
- Health Check: `GET http://localhost:8001/api/v1/health`

### 2. Start the Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
- Local Application: `http://localhost:5173`

### 3. Frontend Production Build
```bash
cd frontend
npm run build
```
Build output is generated into `frontend/dist/`.

### 4. Database & Storage Architecture
- **Relational Database**: Default is asynchronous SQLite (`sqlite+aiosqlite:///./ai_brain.db`). Tables are automatically initialized on startup via `init_db()`. In containerized or cloud deployments, specify a persistent disk path or external database URL in `DATABASE_URL`.
- **Vector Database**: Local Chroma persistence in `./chroma_data` (configurable via `CHROMA_PERSIST_DIRECTORY`).
- **Media & Video Export**: Lectures and animations are rendered and recorded client-side in the browser using Web Audio and Canvas MediaRecorder, exporting WebM video artifacts directly to the learner's device.
- **Security**: The `GEMINI_API_KEY` is strictly server-side and never exposed to the client. Frontend communicates with the backend via `VITE_API_BASE_URL`.

## Document Processing & RAG Usage

```python
from app.services.material_processor import process_document
from app.services.rag_service import rag_service

extracted_doc = process_document("path/to/algorithms.pdf")
await rag_service.ingest_document(extracted_doc)
```

---

## Assessment Intelligence Usage (Phase 5)

```python
from app.services.question_generator import question_generator
from app.services.answer_evaluator import answer_evaluator
from app.services.misconception_detector import misconception_detector
from app.schemas.assessment import StudentAnswer, QuestionType

# 1. Generate Question for a Concept
question = await question_generator.generate_question(
    concept=concept,
    question_type=QuestionType.CONCEPTUAL,
)

# 2. Learner submits an answer
student_ans = StudentAnswer(
    question_id=question.question_id,
    answer_text="Binary search checks elements sequentially from start to end.",
)

# 3. Evaluate answer
eval_result = await answer_evaluator.evaluate_answer(question, student_ans)
print(f"Score: {eval_result.score}, Correct: {eval_result.correctness}")
print(f"Missing Concepts: {eval_result.concepts_missing}")
print(f"Feedback: {eval_result.feedback}")

# 4. Diagnose Misconceptions
analysis = await misconception_detector.detect_misconceptions(
    question=question,
    student_answer=student_ans,
    evaluation_result=eval_result,
    concept=concept,
)

if analysis.detected:
    for m in analysis.misconceptions:
        print(f"Misconception: {m.description} (Severity: {m.severity.value})")
        print(f"Affected Concepts: {m.affected_concept_ids}")
        print(f"Recommended Focus: {m.recommended_focus}")
```

---

## Adaptive Learning Engine Usage (Phase 6)

```python
from app.services.mastery_engine import mastery_engine
from app.services.adaptive_engine import adaptive_engine
from app.schemas.lesson import DifficultyLevel

# 1. Update concept mastery deterministically
updated_mastery = mastery_engine.update_mastery(
    concept_id=concept.concept_id,
    evaluation_result=eval_result,
    previous_mastery=None,  # or existing ConceptMastery
)
print(f"Mastery Score: {updated_mastery.mastery_score}, Level: {updated_mastery.mastery_level.value}")

# 2. Derive next pedagogical action
decision = adaptive_engine.decide_next_action(
    current_concept_id=concept.concept_id,
    current_difficulty=DifficultyLevel.BEGINNER,
    evaluation_result=eval_result,
    concept_mastery=updated_mastery,
    misconception_analysis=analysis,
    concept_graph=concept_graph,
    learner_id="learner_123",
    session_id="session_456",
)

print(f"Action: {decision.action.value}")
print(f"Target Concept: {decision.target_concept_id}")
print(f"Target Difficulty: {decision.target_difficulty.value}")
print(f"Reason: {decision.reason}")
print(f"Evidence: {decision.evidence}")
```

---

## Learner Profile System Usage (Phase 7)

```python
from app.services.learner_profile import learner_profile_service
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel

# 1. Create a learner profile
profile = learner_profile_service.create_profile(
    learner_id="usr_101",
    name="Maya",
    preferred_language=SupportedLanguage.HINGLISH,
    learning_goal="Prepare for competitive exams",
    preferred_difficulty=DifficultyLevel.BEGINNER,
    total_lessons=12,
)

# 2. Update concept mastery and auto-recalculate strengths/weaknesses
learner_profile_service.update_mastery("usr_101", updated_mastery)

# 3. Record lesson progress and assessments
learner_profile_service.record_lesson_completion("usr_101", "lsn_intro_01")
learner_profile_service.record_assessment_result("usr_101", score=0.90)

# 4. View updated profile summary
p = learner_profile_service.get_profile("usr_101")
print(f"Overall Mastery: {p.overall_mastery}")
print(f"Strengths: {p.strengths}")
print(f"Weak Areas: {p.weak_areas}")
print(f"Completed Lessons: {p.completed_lessons}")
print(f"Assessment Average: {p.average_score} (Count: {p.assessment_count})")
```

---

## Phase 7.5 — Developer / Integration Dashboard

The **Developer Dashboard** (`frontend/`) is a React + Vite debug console to inspect, test, and validate the backend pipeline across Phases 1–7.

### Architecture

```text
Browser Dashboard (React + Vite)
        ↓  HTTP REST
FastAPI API Adapters (/api/v1/...)
        ↓
Phase 1–7 Domain Services (Authoritative, Frozen Logic)
        ↓
Structured Models & Responses
```

### Dashboard Modules
1. **System Health** (Phase 1): FastAPI connectivity, version, and subsystem availability.
2. **Material Processing** (Phase 2): Upload PDF, DOCX, PPTX, TXT, view normalized chunks & ChromaDB indexing.
3. **RAG Retrieval** (Phase 3): Semantic vector search, top_k filtering, and grounded prompt context with citations.
4. **Concepts & Graph** (Phase 4): Topic-only or grounded extraction, DFS cycle validation, topological sequence.
5. **Lesson Planner** (Phase 4): Pedagogical syllabus generation and prerequisite sequencing.
6. **Assessment** (Phase 5): Question generation (MCQ, Short Answer, Conceptual, Application), answer evaluation, and misconception diagnosis.
7. **Adaptive Engine** (Phase 6): Interactive simulation of deterministic mastery updating and 6-tier pedagogical decisions.
8. **Learner Profile** (Phase 7): Identity, language preferences, aggregate mastery metrics, strengths/weaknesses, and lesson completion.
9. **Guided End-to-End Pipeline**: 12-step sequential validation with live PASS/FAIL/BLOCKED statuses.
10. **Raw API Inspector & Contracts**: Live HTTP payload inspector with copy buttons and API contract catalog.

### Running Backend & Dashboard

**Terminal 1 — Backend:**
```bash
# Activate virtual environment
.venv\Scripts\activate

# Start FastAPI server
uvicorn main:app --reload --port 8000
```
- Backend URL: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`

**Terminal 2 — Frontend Dashboard:**
```bash
cd frontend
npm install
npm run dev
```
- Dashboard URL: `http://localhost:5173`

---

## Running Tests

Execute the complete regression test suite across Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, and Phase 7.5:
```bash
pytest -v
```

