import hashlib
import logging
import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.exceptions import (
    ConceptCycleError,
    EmptyConceptInputError,
    EmptySyllabusError,
    InvalidConceptError,
    InvalidRelationshipError,
    LessonPlanningError,
)
from app.core.gemini import gemini_client
from app.schemas.lesson import (
    Concept,
    ConceptGraph,
    ConceptRelationshipType,
    DifficultyLevel,
    Lesson,
    RawLessonGrouping,
    RawLessonGroupingResponse,
    Syllabus,
)
from app.schemas.material import ExtractedDocument
from app.services.concept_service import ConceptService, concept_service

logger = logging.getLogger(__name__)

DIFFICULTY_RANK = {
    DifficultyLevel.BEGINNER: 1,
    DifficultyLevel.INTERMEDIATE: 2,
    DifficultyLevel.ADVANCED: 3,
}
RANK_TO_DIFFICULTY = {
    1: DifficultyLevel.BEGINNER,
    2: DifficultyLevel.INTERMEDIATE,
    3: DifficultyLevel.ADVANCED,
}


class LessonPlanner:
    """Domain service for grouping concepts into lessons, sequencing them, and generating complete syllabi."""

    def __init__(
        self,
        concept_svc: Optional[ConceptService] = None,
        client=None,
    ):
        self._concept_service = concept_svc or concept_service
        self._gemini_client = client or gemini_client

    # ----------------------------------------------------------------
    # Deterministic Identifiers
    # ----------------------------------------------------------------

    @staticmethod
    def generate_syllabus_id(
        title: str,
        concept_ids: List[str],
        mode: str,
        material_ids: Optional[List[str]] = None,
    ) -> str:
        """Generate a deterministic SHA-256 syllabus ID based solely on semantic content and mode."""
        if not title or not title.strip():
            raise LessonPlanningError("Cannot generate syllabus ID with an empty title.")
        norm_title = re.sub(r"\s+", " ", title.strip().lower())
        sorted_cids = ",".join(sorted(concept_ids))
        sorted_mids = ",".join(sorted(material_ids or []))
        seed = f"{mode.strip().lower()}:{norm_title}:{sorted_cids}:{sorted_mids}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"syl_{digest}"

    @staticmethod
    def generate_lesson_id(
        title: str,
        sequence_index: int,
        syllabus_id: str,
        concept_ids: Optional[List[str]] = None,
    ) -> str:
        """Generate a deterministic SHA-256 lesson ID."""
        if not title or not title.strip():
            raise LessonPlanningError("Cannot generate lesson ID with an empty title.")
        norm_title = re.sub(r"\s+", " ", title.strip().lower())
        sorted_cids = ",".join(sorted(concept_ids or []))
        seed = f"{syllabus_id}:{sequence_index}:{norm_title}:{sorted_cids}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"lsn_{digest}"

    # ----------------------------------------------------------------
    # High-Level Syllabus Generation (Material-Grounded)
    # ----------------------------------------------------------------

    async def generate_syllabus_from_material(
        self,
        document: ExtractedDocument,
        title: Optional[str] = None,
    ) -> Syllabus:
        """Generate a complete, sequenced, grounded Syllabus from an ExtractedDocument."""
        if not document or not document.chunks:
            raise EmptyConceptInputError("Cannot generate syllabus from an empty document.")

        material_ids = [document.material_id] if document.material_id else []

        # 1. Extract concepts grounded in document chunks
        concepts = await self._concept_service.extract_concepts_from_document(document)
        if not concepts:
            raise EmptyConceptInputError("No concepts were extracted from the document.")

        # 2. Build and validate concept graph (cycle detection happens here)
        concept_graph = self._concept_service.build_concept_graph(concepts)

        # 3. Derive syllabus title if not provided
        course_title = title.strip() if (title and title.strip()) else self._infer_title(document.filename)

        # 4. Generate deterministic syllabus_id
        concept_ids = [c.concept_id for c in concepts]
        syl_id = self.generate_syllabus_id(
            title=course_title,
            concept_ids=concept_ids,
            mode="material_grounded",
            material_ids=material_ids,
        )

        # 5. Group concepts into pedagogical lessons
        raw_lessons = await self.group_concepts_into_lessons(
            concepts=concepts,
            concept_graph=concept_graph,
            syllabus_id=syl_id,
            source_material_ids=material_ids,
        )

        # 6. Sequence lessons topologically respecting concept prerequisites
        sequenced_lessons = self.sequence_lessons(
            lessons=raw_lessons,
            concepts=concepts,
            syllabus_id=syl_id,
        )

        if not sequenced_lessons:
            raise EmptySyllabusError("Lesson planning produced zero valid lessons.")

        return Syllabus(
            syllabus_id=syl_id,
            title=course_title,
            description=f"Pedagogical syllabus for {course_title} covering {len(concepts)} key concepts across {len(sequenced_lessons)} structured lessons.",
            concepts=concepts,
            lessons=sequenced_lessons,
            lesson_ids=[l.lesson_id for l in sequenced_lessons],
            source_material_ids=material_ids,
            is_grounded=True,
            generation_mode="material_grounded",
        )

    # ----------------------------------------------------------------
    # High-Level Syllabus Generation (Topic-Only)
    # ----------------------------------------------------------------

    async def generate_syllabus_from_topic(
        self,
        topic: str,
        title: Optional[str] = None,
    ) -> Syllabus:
        """Generate a complete, sequenced Syllabus for a topic without uploaded source material."""
        if not topic or not topic.strip():
            raise EmptyConceptInputError("Cannot generate syllabus from an empty topic.")

        clean_topic = topic.strip()
        course_title = title.strip() if (title and title.strip()) else clean_topic.title()

        # 1. Extract concepts for topic
        concepts = await self._concept_service.extract_concepts_from_topic(clean_topic)
        if not concepts:
            raise EmptyConceptInputError("No concepts were generated for the topic.")

        # 2. Build and validate concept graph
        concept_graph = self._concept_service.build_concept_graph(concepts)

        # 3. Generate deterministic syllabus_id
        concept_ids = [c.concept_id for c in concepts]
        syl_id = self.generate_syllabus_id(
            title=course_title,
            concept_ids=concept_ids,
            mode="topic_only",
            material_ids=[],
        )

        # 4. Group concepts into pedagogical lessons
        raw_lessons = await self.group_concepts_into_lessons(
            concepts=concepts,
            concept_graph=concept_graph,
            syllabus_id=syl_id,
            source_material_ids=[],
        )

        # 5. Sequence lessons topologically
        sequenced_lessons = self.sequence_lessons(
            lessons=raw_lessons,
            concepts=concepts,
            syllabus_id=syl_id,
        )

        if not sequenced_lessons:
            raise EmptySyllabusError("Lesson planning produced zero valid lessons.")

        return Syllabus(
            syllabus_id=syl_id,
            title=course_title,
            description=f"Curriculum syllabus for {course_title} covering {len(concepts)} core concepts across {len(sequenced_lessons)} structured lessons.",
            concepts=concepts,
            lessons=sequenced_lessons,
            lesson_ids=[l.lesson_id for l in sequenced_lessons],
            source_material_ids=[],
            is_grounded=False,
            generation_mode="topic_only",
        )

    # ----------------------------------------------------------------
    # Pedagogical Lesson Grouping
    # ----------------------------------------------------------------

    async def group_concepts_into_lessons(
        self,
        concepts: List[Concept],
        concept_graph: ConceptGraph,
        syllabus_id: str,
        source_material_ids: Optional[List[str]] = None,
    ) -> List[Lesson]:
        """Group concepts into coherent pedagogical lessons, using LLM grouping when available or deterministic heuristic grouping."""
        if not concepts:
            raise EmptyConceptInputError("Cannot group an empty concept list into lessons.")

        mat_ids = source_material_ids or []
        concept_map = {c.concept_id: c for c in concepts}
        name_to_concept = {c.name.strip().lower(): c for c in concepts}

        # Try LLM grouping if model is available/configured
        grouped_concepts_list: List[List[Concept]] = []
        lesson_meta: List[Dict[str, Any]] = []

        if self._gemini_client.is_configured:
            try:
                system_instruction = (
                    "You are an expert pedagogical curriculum designer.\n"
                    "Group the provided list of academic concepts into a small set of cohesive, structured lessons.\n"
                    "Rules:\n"
                    "1. Group 1 to 4 closely related or dependent concepts per lesson.\n"
                    "2. Do NOT make every concept a separate lesson unless there is only one concept.\n"
                    "3. Ensure all concepts are included in exactly one lesson.\n"
                    "4. Provide a clear lesson title and description."
                )
                concept_summary = "\n".join(
                    [f"- {c.name} (Difficulty: {c.difficulty.value}): {c.description}" for c in concepts]
                )
                prompt = f"Group the following concepts into lessons:\n\n{concept_summary}"

                grouping_response = await self._gemini_client.generate_structured(
                    prompt=prompt,
                    response_schema=RawLessonGroupingResponse,
                    system_instruction=system_instruction,
                )

                assigned_concept_ids: Set[str] = set()
                for rg in grouping_response.lessons:
                    lesson_c_list: List[Concept] = []
                    for c_name in rg.concept_names:
                        clean_c_name = c_name.strip().lower()
                        if clean_c_name in name_to_concept:
                            c_obj = name_to_concept[clean_c_name]
                            if c_obj.concept_id not in assigned_concept_ids:
                                lesson_c_list.append(c_obj)
                                assigned_concept_ids.add(c_obj.concept_id)

                    if lesson_c_list:
                        grouped_concepts_list.append(lesson_c_list)
                        lesson_meta.append({
                            "title": rg.title.strip(),
                            "description": rg.description.strip(),
                            "duration": max(15, min(120, rg.estimated_duration_minutes)),
                        })

                # If some concepts were missed by the LLM, add them to the last lesson or a new lesson
                unassigned = [c for c in concepts if c.concept_id not in assigned_concept_ids]
                if unassigned:
                    if grouped_concepts_list:
                        grouped_concepts_list[-1].extend(unassigned)
                    else:
                        grouped_concepts_list.append(unassigned)
                        lesson_meta.append({
                            "title": f"Core Foundations: {unassigned[0].name}",
                            "description": f"Instructional module covering foundational concepts.",
                            "duration": len(unassigned) * 20,
                        })

            except Exception as e:
                logger.warning(f"LLM lesson grouping failed, falling back to heuristic grouping: {e}")
                grouped_concepts_list = []
                lesson_meta = []

        # Fallback to deterministic topological heuristic grouping
        if not grouped_concepts_list:
            sorted_concepts = self._concept_service.topological_sort(concepts)
            grouped_concepts_list, lesson_meta = self._heuristic_group_concepts(sorted_concepts)

        # Build raw Lesson objects (sequence_index will be finalized in sequencing step)
        lessons: List[Lesson] = []
        for idx, (c_group, meta) in enumerate(zip(grouped_concepts_list, lesson_meta)):
            c_ids = [c.concept_id for c in c_group]
            
            # Aggregate learning objectives
            objs: List[str] = []
            for c in c_group:
                for obj in c.learning_objectives:
                    if obj not in objs:
                        objs.append(obj)

            # Max difficulty of included concepts
            max_rank = max(DIFFICULTY_RANK.get(c.difficulty, 1) for c in c_group)
            lesson_diff = RANK_TO_DIFFICULTY.get(max_rank, DifficultyLevel.BEGINNER)

            lesson_title = meta.get("title") or f"Lesson {idx + 1}: {c_group[0].name}"
            lesson_desc = meta.get("description") or f"Instructional unit covering {', '.join([c.name for c in c_group])}."
            duration = meta.get("duration", max(20, len(c_group) * 20))

            l_id = self.generate_lesson_id(
                title=lesson_title,
                sequence_index=idx,
                syllabus_id=syllabus_id,
                concept_ids=c_ids,
            )

            lessons.append(
                Lesson(
                    lesson_id=l_id,
                    title=lesson_title,
                    description=lesson_desc,
                    concept_ids=c_ids,
                    learning_objectives=objs,
                    prerequisite_lesson_ids=[],
                    difficulty=lesson_diff,
                    estimated_duration_minutes=duration,
                    sequence_index=idx,
                    source_material_ids=mat_ids,
                )
            )

        return lessons

    def _heuristic_group_concepts(
        self,
        sorted_concepts: List[Concept],
    ) -> Tuple[List[List[Concept]], List[Dict[str, Any]]]:
        """Deterministically group sorted concepts into pedagogically cohesive blocks (2-3 per lesson)."""
        grouped: List[List[Concept]] = []
        meta: List[Dict[str, Any]] = []

        if not sorted_concepts:
            return grouped, meta

        # Group into blocks of 2 or 3 concepts
        target_size = 2 if len(sorted_concepts) <= 4 else 3
        current_block: List[Concept] = []

        for c in sorted_concepts:
            current_block.append(c)
            if len(current_block) >= target_size:
                grouped.append(current_block)
                current_block = []

        if current_block:
            if grouped and len(current_block) == 1:
                # Append single remainder to previous lesson to avoid isolated 1-concept lesson
                grouped[-1].extend(current_block)
            else:
                grouped.append(current_block)

        for idx, block in enumerate(grouped):
            names = [c.name for c in block]
            if len(names) == 1:
                title = f"Foundations of {names[0]}"
            else:
                title = f"{names[0]} and {names[-1]}"
            meta.append({
                "title": title,
                "description": f"Explores key concepts: {', '.join(names)}.",
                "duration": max(20, min(90, len(block) * 20)),
            })

        return grouped, meta

    # ----------------------------------------------------------------
    # Lesson Sequencing & Prerequisite Inference
    # ----------------------------------------------------------------

    def sequence_lessons(
        self,
        lessons: List[Lesson],
        concepts: List[Concept],
        syllabus_id: str,
    ) -> List[Lesson]:
        """Sequence lessons in topological order based on concept prerequisite relationships."""
        if not lessons:
            return []

        # 1. Map concept ID to its lesson index
        concept_to_lesson_idx: Dict[str, int] = {}
        for l_idx, lesson in enumerate(lessons):
            for c_id in lesson.concept_ids:
                concept_to_lesson_idx[c_id] = l_idx

        concept_map = {c.concept_id: c for c in concepts}

        # 2. Build directed lesson dependency graph
        lesson_adj: Dict[int, Set[int]] = defaultdict(set)
        lesson_in_degree: Dict[int, int] = {i: 0 for i in range(len(lessons))}

        for l_idx, lesson in enumerate(lessons):
            for c_id in lesson.concept_ids:
                concept = concept_map.get(c_id)
                if not concept:
                    continue
                for prereq_c_id in concept.prerequisite_concept_ids:
                    prereq_l_idx = concept_to_lesson_idx.get(prereq_c_id)
                    if prereq_l_idx is not None and prereq_l_idx != l_idx:
                        if l_idx not in lesson_adj[prereq_l_idx]:
                            lesson_adj[prereq_l_idx].add(l_idx)
                            lesson_in_degree[l_idx] += 1

        # 3. Detect lesson cycles and topological sort
        zero_in_degree = [i for i, deg in lesson_in_degree.items() if deg == 0]
        # Deterministic sorting
        zero_in_degree.sort(key=lambda i: (
            DIFFICULTY_RANK.get(lessons[i].difficulty, 1),
            lessons[i].title.lower(),
        ))

        queue = deque(zero_in_degree)
        ordered_indices: List[int] = []

        while queue:
            curr = queue.popleft()
            ordered_indices.append(curr)

            for neighbor in sorted(lesson_adj[curr]):
                lesson_in_degree[neighbor] -= 1
                if lesson_in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered_indices) != len(lessons):
            raise ConceptCycleError("Circular prerequisite dependency detected between grouped lessons.")

        # 4. Map old index to new sequence and update lesson attributes
        reordered_lessons: List[Lesson] = []
        old_idx_to_new_lesson_id: Dict[int, str] = {}

        for new_seq, old_idx in enumerate(ordered_indices):
            orig_lesson = lessons[old_idx]
            new_id = self.generate_lesson_id(
                title=orig_lesson.title,
                sequence_index=new_seq,
                syllabus_id=syllabus_id,
                concept_ids=orig_lesson.concept_ids,
            )
            old_idx_to_new_lesson_id[old_idx] = new_id

        for new_seq, old_idx in enumerate(ordered_indices):
            orig_lesson = lessons[old_idx]
            new_id = old_idx_to_new_lesson_id[old_idx]

            # Invert incoming dependencies to find prerequisite lesson IDs
            prereq_lesson_ids = []
            for other_old_idx, targets in lesson_adj.items():
                if old_idx in targets:
                    prereq_id = old_idx_to_new_lesson_id[other_old_idx]
                    if prereq_id not in prereq_lesson_ids:
                        prereq_lesson_ids.append(prereq_id)

            reordered_lessons.append(
                Lesson(
                    lesson_id=new_id,
                    title=orig_lesson.title,
                    description=orig_lesson.description,
                    concept_ids=orig_lesson.concept_ids,
                    learning_objectives=orig_lesson.learning_objectives,
                    prerequisite_lesson_ids=sorted(prereq_lesson_ids),
                    difficulty=orig_lesson.difficulty,
                    estimated_duration_minutes=orig_lesson.estimated_duration_minutes,
                    sequence_index=new_seq,
                    source_material_ids=orig_lesson.source_material_ids,
                )
            )

        return reordered_lessons

    # ----------------------------------------------------------------
    # Utility Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _infer_title(filename: Optional[str]) -> str:
        """Infer a course title from document filename."""
        if not filename:
            return "Course Syllabus"
        stem = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)
        stem = re.sub(r"[_\-]+", " ", stem).strip()
        return stem.title() or "Course Syllabus"

    def create_time_adaptive_syllabus(
        self,
        concept_graph: ConceptGraph,
        title: str,
        available_time_minutes: int = 20,
        desired_depth: str = "standard",
        material_id: Optional[str] = None,
    ) -> Syllabus:
        """Construct a time-budgeted adaptive syllabus calibrated for 5m, 20m, or 60m learning blocks."""
        from app.services.time_adaptive_planner import time_adaptive_planner
        return time_adaptive_planner.create_time_budgeted_syllabus(
            concept_graph=concept_graph,
            title=title,
            available_time_minutes=available_time_minutes,
            desired_depth=desired_depth,
            material_id=material_id,
        )


# Singleton lesson planner instance
lesson_planner = LessonPlanner()
