"""
Service for generating comprehensive final assessments and diagnostic learning reports.

Features:
1. Multi-concept final assessment generation covering targeted curricula.
2. Comprehensive multi-question evaluation with concept-level scoring.
3. Diagnostic misconception aggregation across all questions.
4. Multilingual pedagogical reporting (English, Hindi, Hinglish) detailing strengths,
   weaknesses, and actionable study recommendations.
5. Persistent audit logging: writes AssessmentAttempt records, updates learner running
   average and assessment count, updates concept mastery records, and logs learning events.
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AssessmentError, TeacherSessionError
from app.db.repository import LearnerRepository
from app.db.session import get_db_session
from app.core.gemini import GeminiClient, gemini_client
from app.schemas.adaptive import ConceptMastery, MasteryLevel
from app.schemas.assessment import (
    AssessmentReport,
    ConceptReportItem,
    EvaluationResult,
    FinalAssessmentPackage,
    FinalAssessmentRequest,
    FinalAssessmentSubmission,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
    Question,
    QuestionType,
    RawAssessmentReportPayload,
    StudentAnswer,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import Concept, DifficultyLevel
from app.services.answer_evaluator import AnswerEvaluator, answer_evaluator
from app.services.concept_service import ConceptService, concept_service
from app.services.mastery_engine import MasteryEngine, mastery_engine
from app.services.misconception_detector import (
    MisconceptionDetector,
    misconception_detector,
)
from app.services.question_generator import (
    QuestionGenerator,
    question_generator,
)

logger = logging.getLogger(__name__)


class AssessmentReportService:
    """Domain service orchestrating post-lesson/post-course assessments and learning reports."""

    def __init__(
        self,
        gemini_client_instance: Optional[GeminiClient] = None,
        question_gen: Optional[QuestionGenerator] = None,
        answer_eval: Optional[AnswerEvaluator] = None,
        misc_det: Optional[MisconceptionDetector] = None,
        concept_svc: Optional[ConceptService] = None,
        mastery_eng: Optional[MasteryEngine] = None,
    ):
        self._gemini_client = gemini_client_instance or gemini_client
        self._question_generator = question_gen or question_generator
        self._answer_evaluator = answer_eval or answer_evaluator
        self._misconception_detector = misc_det or misconception_detector
        self._concept_service = concept_svc or concept_service
        self._mastery_engine = mastery_eng or mastery_engine
        # In-memory store for generated assessment packages: assessment_id -> FinalAssessmentPackage
        self._package_cache: Dict[str, FinalAssessmentPackage] = {}

    # --------------------------------------------------------------------
    # Assessment Generation
    # --------------------------------------------------------------------

    async def generate_assessment(
        self,
        request: FinalAssessmentRequest,
    ) -> FinalAssessmentPackage:
        """Generate a balanced multi-question assessment package across requested concepts."""
        if not request.learner_id:
            raise AssessmentError("learner_id is required for assessment generation.")

        concept_ids = list(request.concept_ids)
        if not concept_ids:
            if request.lesson_id:
                # Attempt to discover concepts from concept service
                discovered = self._concept_service.list_concepts_for_lesson(request.lesson_id)
                concept_ids = [c.concept_id for c in discovered]
            if not concept_ids:
                concept_ids = ["cpt_core_principles"]

        num_q = max(1, min(20, request.num_questions))
        questions: List[Question] = []

        # Distribute question generation round-robin across concept IDs
        for i in range(num_q):
            cid = concept_ids[i % len(concept_ids)]
            c_name = cid.replace("cpt_", "").replace("_", " ").title()
            c_obj = None
            if hasattr(self._concept_service, "get_concept"):
                c_obj = self._concept_service.get_concept(cid)
                if c_obj:
                    c_name = c_obj.name
            if c_obj is None:
                c_obj = Concept(
                    concept_id=cid,
                    name=c_name,
                    description=f"Assessment concept: {c_name}",
                    difficulty=request.difficulty,
                    learning_objectives=[f"Assess core competencies in {c_name}"],
                )

            # Alternate between MCQ and CONCEPTUAL question types
            q_type = QuestionType.MCQ if (i % 2 == 1) else QuestionType.CONCEPTUAL

            try:
                q = await self._question_generator.generate_question(
                    concept=c_obj,
                    question_type=q_type,
                    learning_objective=f"Assess mastery of {c_obj.name}",
                    lesson_id=request.lesson_id,
                )
                questions.append(q)
            except Exception as ex:
                logger.warning("Question generation failed for concept %s: %s, using fallback", cid, ex)
                fallback_q = self._build_fallback_question(
                    concept_id=cid,
                    concept_name=c_obj.name,
                    question_type=q_type,
                    difficulty=request.difficulty,
                    language=request.language,
                    lesson_id=request.lesson_id,
                    index=i,
                )
                questions.append(fallback_q)

        assessment_id = f"asm_{uuid.uuid4().hex[:16]}"
        package = FinalAssessmentPackage(
            assessment_id=assessment_id,
            learner_id=request.learner_id,
            lesson_id=request.lesson_id,
            session_id=request.session_id,
            questions=questions,
            total_questions=len(questions),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._package_cache[assessment_id] = package
        return package

    # --------------------------------------------------------------------
    # Assessment Evaluation & Reporting
    # --------------------------------------------------------------------

    async def evaluate_assessment(
        self,
        submission: FinalAssessmentSubmission,
        questions: Optional[List[Question]] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> AssessmentReport:
        """Evaluate student answers, diagnose flaws, calculate scores, and generate diagnostic report."""
        if not submission.learner_id:
            raise AssessmentError("learner_id is required for assessment evaluation.")

        # Resolve questions
        resolved_questions: List[Question] = []
        if questions:
            resolved_questions = questions
        elif submission.assessment_id in self._package_cache:
            resolved_questions = self._package_cache[submission.assessment_id].questions
        else:
            # Construct dummy questions based on student answers if questions are not in memory
            for ans in submission.answers:
                resolved_questions.append(
                    Question(
                        question_id=ans.question_id,
                        question_type=QuestionType.CONCEPTUAL,
                        question_text=f"Question {ans.question_id}",
                        concept_id=getattr(ans, "concept_id", "cpt_general") or "cpt_general",
                        difficulty=DifficultyLevel.INTERMEDIATE,
                        learning_objective="Evaluate answer",
                        options=[],
                        correct_answer="Expected standard reference response.",
                        explanation="Evaluated against domain criteria.",
                    )
                )

        if not resolved_questions:
            raise AssessmentError(f"No questions found for assessment '{submission.assessment_id}'.")

        q_map: Dict[str, Question] = {q.question_id: q for q in resolved_questions}

        # Evaluate each submitted answer
        eval_results: List[EvaluationResult] = []
        misconceptions_detected: List[Misconception] = []
        concept_scores: Dict[str, List[float]] = {}
        correct_count = 0

        for ans in submission.answers:
            q = q_map.get(ans.question_id)
            if not q:
                continue

            try:
                eval_res = await self._answer_evaluator.evaluate_answer(
                    question=q,
                    student_answer=ans,
                )
            except Exception as ex:
                logger.warning("Answer evaluation failed for question %s: %s, using deterministic eval", q.question_id, ex)
                eval_res = self._build_fallback_eval_result(q, ans)

            eval_results.append(eval_res)
            if eval_res.score >= 0.75:
                correct_count += 1

            cid = q.concept_id
            if cid not in concept_scores:
                concept_scores[cid] = []
            concept_scores[cid].append(eval_res.score)

            # If score indicates flaws (< 0.75), diagnose potential misconceptions
            if eval_res.score < 0.75:
                try:
                    c_obj = self._concept_service.get_concept(cid) if hasattr(self._concept_service, "get_concept") else None
                    analysis: MisconceptionAnalysis = await self._misconception_detector.detect_misconceptions(
                        question=q,
                        student_answer=ans,
                        evaluation_result=eval_res,
                        concept=c_obj,
                    )
                    if analysis.detected and analysis.misconceptions:
                        misconceptions_detected.extend(analysis.misconceptions)
                except Exception as ex:
                    logger.warning("Misconception detection failed on assessment: %s", ex)

        total_q = len(eval_results) if eval_results else 1
        overall_score = round(sum(e.score for e in eval_results) / total_q, 4)
        overall_mastery = self._derive_mastery_level(overall_score)
        letter_grade = self._derive_letter_grade(overall_score)

        # Build concept breakdowns
        concept_breakdowns: List[ConceptReportItem] = []
        for cid, scores in concept_scores.items():
            avg_s = round(sum(scores) / len(scores), 4)
            c_name = cid.replace("cpt_", "").replace("_", " ").title()
            if hasattr(self._concept_service, "get_concept"):
                c_obj = self._concept_service.get_concept(cid)
                if c_obj:
                    c_name = c_obj.name

            c_mastery = self._derive_mastery_level(avg_s)
            status = "mastered" if avg_s >= 0.85 else ("in_progress" if avg_s >= 0.60 else "needs_review")
            concept_breakdowns.append(
                ConceptReportItem(
                    concept_id=cid,
                    concept_name=c_name,
                    score=avg_s,
                    mastery_level=c_mastery,
                    status=status,
                    attempts=len(scores),
                )
            )

        # Generate diagnostic strengths, weaknesses, recommendations, and summary
        raw_report = await self._synthesize_report_narrative(
            overall_score=overall_score,
            letter_grade=letter_grade,
            concept_breakdowns=concept_breakdowns,
            misconceptions=misconceptions_detected,
            language=submission.language,
        )

        report_id = f"rpt_{uuid.uuid4().hex[:16]}"
        report = AssessmentReport(
            report_id=report_id,
            learner_id=submission.learner_id,
            session_id=submission.session_id,
            lesson_id=submission.lesson_id,
            overall_score=overall_score,
            overall_mastery_level=overall_mastery,
            letter_grade=letter_grade,
            total_questions=len(eval_results),
            correct_answers=correct_count,
            concept_breakdowns=concept_breakdowns,
            misconceptions_detected=misconceptions_detected,
            strengths=raw_report.strengths,
            weaknesses=raw_report.weaknesses,
            recommendations=raw_report.recommendations,
            summary=raw_report.summary,
            language=submission.language,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Persist assessment attempts, scores, and events to DB
        async def _persist_report(s: AsyncSession):
            repo = LearnerRepository(s)
            # Record individual assessment attempts
            for e in eval_results:
                q = q_map.get(e.question_id)
                q_type_str = q.question_type.value if q else "conceptual"
                rubric_str = q.evaluation_rubric if q else None
                try:
                    await repo.record_assessment_attempt(
                        evaluation_id=e.evaluation_id,
                        learner_id=submission.learner_id,
                        question_id=e.question_id,
                        concept_id=e.concept_id,
                        question_type=q_type_str,
                        student_answer=e.student_answer,
                        score=e.score,
                        correctness=e.correctness,
                        confidence=e.confidence,
                        session_id=submission.session_id,
                        concepts_demonstrated=e.concepts_demonstrated,
                        concepts_missing=e.concepts_missing,
                        misconception_diagnosed=e.feedback if not e.correctness else None,
                        evaluation_rubric=rubric_str,
                    )
                except Exception as ex:
                    logger.warning("Could not persist attempt %s: %s", e.evaluation_id, ex)

            # Update learner cumulative assessment stats
            try:
                await repo.record_assessment_score(submission.learner_id, overall_score)
            except Exception as ex:
                logger.warning("Could not update learner assessment score: %s", ex)

            # Upsert concept masteries
            for cb in concept_breakdowns:
                try:
                    c_mastery_obj = ConceptMastery(
                        concept_id=cb.concept_id,
                        mastery_score=cb.score,
                        mastery_level=cb.mastery_level,
                        confidence=0.9,
                        attempts=cb.attempts,
                        correct_attempts=1 if cb.score >= 0.75 else 0,
                        partial_attempts=1 if 0.25 <= cb.score < 0.75 else 0,
                        incorrect_attempts=1 if cb.score < 0.25 else 0,
                        last_score=cb.score,
                    )
                    await repo.upsert_concept_mastery(submission.learner_id, c_mastery_obj)
                except Exception as ex:
                    logger.warning("Could not upsert concept mastery for %s: %s", cb.concept_id, ex)

            # Log learning event
            await repo.log_learning_event(
                learner_id=submission.learner_id,
                session_id=submission.session_id,
                concept_id=concept_breakdowns[0].concept_id if concept_breakdowns else None,
                event_type="FINAL_ASSESSMENT_COMPLETED",
                payload={
                    "report_id": report_id,
                    "overall_score": overall_score,
                    "letter_grade": letter_grade,
                    "total_questions": len(eval_results),
                    "correct_answers": correct_count,
                    "language": submission.language.value,
                },
            )

        try:
            if db_session is not None:
                await _persist_report(db_session)
            else:
                async with get_db_session() as s:
                    await _persist_report(s)
        except Exception as ex:
            logger.error("Failed to persist assessment report to DB: %s", ex)

        return report

    # --------------------------------------------------------------------
    # Synthesis & Multilingual Report Generation
    # --------------------------------------------------------------------

    async def _synthesize_report_narrative(
        self,
        overall_score: float,
        letter_grade: str,
        concept_breakdowns: List[ConceptReportItem],
        misconceptions: List[Misconception],
        language: SupportedLanguage,
    ) -> RawAssessmentReportPayload:
        """Use Gemini LLM with structured schema or fallback generator to craft report narrative."""
        lang_directive = self._get_language_directive(language)
        concept_summary = ", ".join(f"{c.concept_name}: {int(c.score * 100)}% ({c.status})" for c in concept_breakdowns)
        misc_summary = "; ".join(f"{m.description} (Severity: {m.severity.value})" for m in misconceptions) or "None detected"

        system_instruction = (
            "You are a Senior Pedagogical Evaluator for an AI Teacher.\n"
            f"Instructional Language Directive: {lang_directive}\n"
            "Analyze the final assessment data and formulate an encouraging, diagnostic report.\n"
            "Include:\n"
            "1. An executive summary characterizing overall learner performance.\n"
            "2. 2-4 key conceptual strengths.\n"
            "3. 1-3 targeted weaknesses or topics needing review.\n"
            "4. 2-4 actionable next-step study recommendations."
        )

        prompt = (
            f"Overall Score: {int(overall_score * 100)}%\n"
            f"Grade: {letter_grade}\n"
            f"Concept Breakdown: {concept_summary}\n"
            f"Diagnosed Misconceptions: {misc_summary}\n\n"
            "Generate the comprehensive assessment summary, strengths, weaknesses, and recommendations."
        )

        try:
            raw: RawAssessmentReportPayload = await self._gemini_client.generate_structured(
                prompt=prompt,
                response_schema=RawAssessmentReportPayload,
                system_instruction=system_instruction,
            )
            return raw
        except Exception as ex:
            logger.warning("LLM report narrative generation failed: %s, using fallback", ex)
            return self._build_fallback_narrative(overall_score, letter_grade, concept_breakdowns, misconceptions, language)

    @staticmethod
    def _get_language_directive(language: SupportedLanguage) -> str:
        if language == SupportedLanguage.HINDI:
            return "Write entirely in natural, academic Hindi using Devanagari script."
        elif language == SupportedLanguage.HINGLISH:
            return "Write in conversational Hinglish (blend of Hindi and English in Latin script), widely used in Indian tech classrooms."
        return "Write in clear, encouraging, academic English."

    def _build_fallback_narrative(
        self,
        overall_score: float,
        letter_grade: str,
        concept_breakdowns: List[ConceptReportItem],
        misconceptions: List[Misconception],
        language: SupportedLanguage,
    ) -> RawAssessmentReportPayload:
        pct = int(overall_score * 100)
        strong_concepts = [c.concept_name for c in concept_breakdowns if c.score >= 0.75]
        weak_concepts = [c.concept_name for c in concept_breakdowns if c.score < 0.75]

        if language == SupportedLanguage.HINDI:
            summary = f"अंतिम मूल्यांकन संपन्न हुआ। छात्र ने {pct}% अंक और ग्रेड '{letter_grade}' प्राप्त किया है।"
            strengths = [f"{c} में मजबूत वैचारिक स्पष्टता" for c in strong_concepts] or ["बुनियादी सिद्धांतों की समझ"]
            weaknesses = [f"{c} के सिद्धांतों का पुनः अभ्यास आवश्यक है" for c in weak_concepts] or ["कोई गंभीर कमजोरी नहीं"]
            recs = [
                "कमजोर अवधारणाओं के लिए व्यावहारिक अभ्यास करें।",
                "एल्गोरिदम और डेटा संरचनाओं के कोड निष्पादन का अभ्यास करें।",
            ]
        elif language == SupportedLanguage.HINGLISH:
            summary = f"Assessment successfully complete ho gaya! Aapne {pct}% score kiya aur grade '{letter_grade}' achieve kiya."
            strengths = [f"{c} me clear understanding aur solid grasp demonstrate kiya" for c in strong_concepts] or ["Fundamental conceptual concepts clear hain"]
            weaknesses = [f"{c} ke edge cases aur core mechanisms pe thoda aur revision chahiye" for c in weak_concepts] or ["Koi major weak area nahi mila"]
            recs = [
                "Weak topics ke liye step-by-step code trace aur practice problems solve kijiye.",
                "Spaced repetition schedule follow karke retention strong rakhein.",
            ]
        else:
            summary = f"Assessment completed successfully with an overall score of {pct}% (Grade: {letter_grade})."
            strengths = [f"Strong conceptual mastery of {c}" for c in strong_concepts] or ["Solid grasp of foundational principles"]
            weaknesses = [f"Requires further review and reinforcement in {c}" for c in weak_concepts] or ["No significant conceptual gaps identified"]
            recs = [
                "Review targeted remediation notes for any concepts marked for review.",
                "Implement hands-on practice problems to solidify theoretical invariants.",
                "Schedule spaced repetition reviews within the next 48 to 72 hours.",
            ]

        return RawAssessmentReportPayload(
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recs,
        )

    # --------------------------------------------------------------------
    # Helper & Deterministic Fallbacks
    # --------------------------------------------------------------------

    @staticmethod
    def _derive_letter_grade(score: float) -> str:
        if score >= 0.90:
            return "A+"
        elif score >= 0.80:
            return "A"
        elif score >= 0.70:
            return "B"
        elif score >= 0.60:
            return "C"
        elif score >= 0.50:
            return "D"
        return "F"

    @staticmethod
    def _derive_mastery_level(score: float) -> MasteryLevel:
        if score >= 0.85:
            return MasteryLevel.MASTERED
        elif score >= 0.70:
            return MasteryLevel.PROFICIENT
        elif score >= 0.50:
            return MasteryLevel.DEVELOPING
        elif score >= 0.25:
            return MasteryLevel.EMERGING
        return MasteryLevel.NOT_STARTED

    def _build_fallback_question(
        self,
        concept_id: str,
        concept_name: str,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        language: SupportedLanguage,
        lesson_id: Optional[str],
        index: int,
    ) -> Question:
        if language == SupportedLanguage.HINDI:
            q_text = f"{concept_name} के प्रमुख नियमों और कार्यप्रणाली का वर्णन करें।"
            ans = f"{concept_name} प्रणाली को कुशलतापूर्वक प्रबंधित करने के लिए आवश्यक है।"
        elif language == SupportedLanguage.HINGLISH:
            q_text = f"{concept_name} ka primary mechanism aur implementation logic explain kijiye."
            ans = f"{concept_name} efficiently operations handle karne ke liye primary construct hai."
        else:
            q_text = f"Explain the core mechanisms and design invariants of {concept_name}."
            ans = f"{concept_name} provides systematic operation and preserves algorithmic correctness."

        options: List[str] = []
        if question_type == QuestionType.MCQ:
            options = [
                f"Option A: Correct application of {concept_name}",
                f"Option B: Linear scan without {concept_name}",
                f"Option C: Unbounded growth without termination",
                f"Option D: Random permutation",
            ]
            ans = options[0]

        q_id = f"qst_final_{hashlib.sha256(f'{concept_id}:{index}:{q_text}'.encode()).hexdigest()[:12]}"
        return Question(
            question_id=q_id,
            question_type=question_type,
            question_text=q_text,
            concept_id=concept_id,
            lesson_id=lesson_id,
            difficulty=difficulty,
            learning_objective=f"Evaluate mastery of {concept_name}",
            options=options,
            correct_answer=ans,
            explanation=f"Understanding {concept_name} is essential for problem-solving.",
        )

    def _build_fallback_eval_result(
        self,
        question: Question,
        student_answer: StudentAnswer,
    ) -> EvaluationResult:
        given = (student_answer.answer_text or student_answer.selected_option or "").strip()
        score = 0.8 if len(given) > 15 else 0.4
        correct = score >= 0.75
        digest = hashlib.sha256(f"{question.question_id}:{given}".encode()).hexdigest()[:12]

        return EvaluationResult(
            evaluation_id=f"eval_fb_{digest}",
            question_id=question.question_id,
            concept_id=question.concept_id,
            correctness=correct,
            score=score,
            confidence=0.85,
            expected_answer=question.correct_answer,
            student_answer=given,
            concepts_tested=[question.concept_id],
            concepts_demonstrated=[question.concept_id] if correct else [],
            concepts_missing=[] if correct else [question.concept_id],
            evidence=f"Evaluated input: '{given[:50]}...'",
            feedback="Good effort. Review core definitions to strengthen complete conceptual precision." if not correct else "Great answer!",
        )


assessment_report_service = AssessmentReportService()
