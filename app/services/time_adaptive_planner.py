import hashlib
import logging
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.exceptions import (
    EmptyConceptInputError,
    EmptySyllabusError,
    LessonPlanningError,
)
from app.schemas.lesson import (
    Concept,
    ConceptGraph,
    ConceptRelationshipType,
    DifficultyLevel,
    Lesson,
    Syllabus,
)
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


class TimeAdaptivePlanner:
    """Domain service for intelligent curriculum pruning, time-budget calibration,
    and depth-adaptive syllabus construction (5 min / 20 min / 60 min).
    """

    def __init__(self, concept_svc: Optional[ConceptService] = None):
        self._concept_service = concept_svc or concept_service

    # --------------------------------------------------------------------
    # Concept Pruning & Prioritization
    # --------------------------------------------------------------------

    def prune_and_prioritize_concepts(
        self,
        concept_graph: ConceptGraph,
        available_time_minutes: int,
        desired_depth: str = "standard",
    ) -> List[Concept]:
        """Select and prioritize concepts respecting time constraints and prerequisite integrity.
        
        Rules:
        - 5-minute / quick_overview (<= 10 min): 1 to 2 foundational concepts.
        - 20-minute / standard (11 to 35 min): 3 to 5 core concepts in topological order.
        - 60-minute / deep_dive (> 35 min): Comprehensive retention of all reachable concepts.
        - Prerequisite Closure: If concept C is included, all prerequisite concepts of C MUST be included.
        """
        if not concept_graph or not concept_graph.concepts:
            raise EmptyConceptInputError("Cannot plan curriculum from empty concept graph.")

        all_concepts = concept_graph.concepts
        concept_map = {c.concept_id: c for c in all_concepts}

        # 1. Topological sequence ensures prerequisite ordering
        topo_concepts = self._concept_service.topological_sort(
            all_concepts,
            concept_graph.relationships,
        )

        total_available = len(topo_concepts)
        time = max(1, available_time_minutes)

        # 2. Determine target concept capacity
        if time <= 10 or desired_depth == "quick_overview":
            target_count = min(2, total_available)
        elif time <= 35 or desired_depth == "standard":
            target_count = min(5, max(3, total_available)) if total_available >= 3 else total_available
        else:
            # 60-minute deep dive
            target_count = total_available

        if target_count >= total_available:
            return topo_concepts

        # 3. Graph-theoretic centrality ranking
        # Build prerequisite dependencies graph
        prereq_of: Dict[str, Set[str]] = defaultdict(set)
        depends_on: Dict[str, Set[str]] = defaultdict(set)

        for rel in concept_graph.relationships:
            if rel.relationship_type == ConceptRelationshipType.PREREQUISITE:
                prereq_of[rel.source_concept_id].add(rel.target_concept_id)
                depends_on[rel.target_concept_id].add(rel.source_concept_id)

        # Concepts also specify prerequisite_concept_ids directly
        for c in all_concepts:
            for pid in c.prerequisite_concept_ids:
                if pid in concept_map:
                    depends_on[c.concept_id].add(pid)
                    prereq_of[pid].add(c.concept_id)

        # Score concepts: foundational (roots, high out-degree) scored highest
        def concept_priority(c: Concept) -> float:
            score = 100.0
            # Higher out-degree (unlocks more concepts) = higher priority
            score += len(prereq_of[c.concept_id]) * 15.0
            # Lower difficulty = earlier foundation
            score -= DIFFICULTY_RANK.get(c.difficulty, 2) * 5.0
            # Fewer dependencies = more foundational
            score -= len(depends_on[c.concept_id]) * 3.0
            return score

        ranked_concepts = sorted(topo_concepts, key=concept_priority, reverse=True)

        # 4. Greedy selection with strict prerequisite closure
        selected_ids: Set[str] = set()

        def add_with_prerequisites(cid: str) -> None:
            # Recursively ensure all transitive prerequisites are included
            queue = deque([cid])
            while queue:
                curr = queue.popleft()
                if curr not in selected_ids and curr in concept_map:
                    selected_ids.add(curr)
                    for pid in depends_on[curr]:
                        if pid not in selected_ids:
                            queue.append(pid)

        for candidate in ranked_concepts:
            if len(selected_ids) >= target_count:
                break
            add_with_prerequisites(candidate.concept_id)
            if len(selected_ids) >= target_count:
                # Trim if prerequisite closure expanded beyond target_count
                break

        # If for some reason we have fewer than target_count, pick in topological order
        if len(selected_ids) < target_count:
            for c in topo_concepts:
                if c.concept_id not in selected_ids:
                    add_with_prerequisites(c.concept_id)
                    if len(selected_ids) >= target_count:
                        break

        # 5. Return final selected concepts filtered and ordered according to topological sequence
        final_list = [c for c in topo_concepts if c.concept_id in selected_ids]
        return final_list

    # --------------------------------------------------------------------
    # Time-Budgeted Syllabus Synthesis
    # --------------------------------------------------------------------

    def create_time_budgeted_syllabus(
        self,
        concept_graph: ConceptGraph,
        title: str,
        available_time_minutes: int,
        desired_depth: str = "standard",
        material_id: Optional[str] = None,
    ) -> Syllabus:
        """Create a complete sequenced Syllabus matching the available time budget."""
        if not concept_graph or not concept_graph.concepts:
            raise EmptySyllabusError("Cannot create syllabus from empty concept graph.")

        time = max(5, available_time_minutes)
        prioritized = self.prune_and_prioritize_concepts(
            concept_graph=concept_graph,
            available_time_minutes=time,
            desired_depth=desired_depth,
        )

        clean_title = title.strip() if title and title.strip() else "Adaptive Curriculum"
        seed = f"{clean_title}:{time}:{desired_depth}:{len(prioritized)}"
        syllabus_id = f"syl_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"

        # Group concepts into lessons calibrated to time budget
        lessons: List[Lesson] = []

        if time <= 10 or desired_depth == "quick_overview":
            # 5-10 minute lesson: single high-impact lesson
            c_ids = [c.concept_id for c in prioritized]
            objs = self._collect_objectives(prioritized)
            max_diff = self._max_difficulty(prioritized)
            l_id = f"lsn_{hashlib.sha256(f'{syllabus_id}:0'.encode()).hexdigest()[:16]}"

            lessons.append(
                Lesson(
                    lesson_id=l_id,
                    title=f"Quick Overview: {prioritized[0].name}",
                    description=f"Concise 5-minute foundational overview of {prioritized[0].name}.",
                    concept_ids=c_ids,
                    learning_objectives=objs,
                    prerequisite_lesson_ids=[],
                    difficulty=max_diff,
                    estimated_duration_minutes=time,
                    sequence_index=0,
                    source_material_ids=[material_id] if material_id else [],
                )
            )

        elif time <= 35 or desired_depth == "standard":
            # 20-minute lesson: 1 or 2 balanced modules
            if len(prioritized) <= 2:
                # 1 lesson covering all 20 min
                c_ids = [c.concept_id for c in prioritized]
                l_id = f"lsn_{hashlib.sha256(f'{syllabus_id}:0'.encode()).hexdigest()[:16]}"
                lessons.append(
                    Lesson(
                        lesson_id=l_id,
                        title=f"Core Study: {prioritized[0].name}",
                        description=f"Standard 20-minute module exploring core mechanics and intuition.",
                        concept_ids=c_ids,
                        learning_objectives=self._collect_objectives(prioritized),
                        prerequisite_lesson_ids=[],
                        difficulty=self._max_difficulty(prioritized),
                        estimated_duration_minutes=time,
                        sequence_index=0,
                        source_material_ids=[material_id] if material_id else [],
                    )
                )
            else:
                # Split into 2 lessons (e.g. 10m + 10m)
                mid = len(prioritized) // 2
                grp1 = prioritized[:mid]
                grp2 = prioritized[mid:]
                dur1 = time // 2
                dur2 = time - dur1

                l_id1 = f"lsn_{hashlib.sha256(f'{syllabus_id}:0'.encode()).hexdigest()[:16]}"
                l_id2 = f"lsn_{hashlib.sha256(f'{syllabus_id}:1'.encode()).hexdigest()[:16]}"

                lessons.append(
                    Lesson(
                        lesson_id=l_id1,
                        title=f"Part 1: {grp1[0].name} Foundations",
                        description=f"First module covering foundational concepts.",
                        concept_ids=[c.concept_id for c in grp1],
                        learning_objectives=self._collect_objectives(grp1),
                        prerequisite_lesson_ids=[],
                        difficulty=self._max_difficulty(grp1),
                        estimated_duration_minutes=dur1,
                        sequence_index=0,
                        source_material_ids=[material_id] if material_id else [],
                    )
                )
                lessons.append(
                    Lesson(
                        lesson_id=l_id2,
                        title=f"Part 2: {grp2[0].name} & Applications",
                        description=f"Second module covering application and synthesis.",
                        concept_ids=[c.concept_id for c in grp2],
                        learning_objectives=self._collect_objectives(grp2),
                        prerequisite_lesson_ids=[l_id1],
                        difficulty=self._max_difficulty(grp2),
                        estimated_duration_minutes=dur2,
                        sequence_index=1,
                        source_material_ids=[material_id] if material_id else [],
                    )
                )

        else:
            # 60-minute deep dive: 3 or 4 structured lessons
            num_lessons = min(3, len(prioritized)) if len(prioritized) >= 3 else 2
            chunk_size = max(1, len(prioritized) // num_lessons)
            dur_per_lesson = time // num_lessons

            prev_lid = None
            for idx in range(num_lessons):
                start = idx * chunk_size
                end = (idx + 1) * chunk_size if idx < num_lessons - 1 else len(prioritized)
                c_grp = prioritized[start:end]
                if not c_grp:
                    continue

                cur_dur = dur_per_lesson if idx < num_lessons - 1 else (time - dur_per_lesson * (num_lessons - 1))
                cur_lid = f"lsn_{hashlib.sha256(f'{syllabus_id}:{idx}'.encode()).hexdigest()[:16]}"

                lessons.append(
                    Lesson(
                        lesson_id=cur_lid,
                        title=f"Module {idx + 1}: {c_grp[0].name}",
                        description=f"Deep dive module {idx + 1} covering {', '.join(c.name for c in c_grp)}.",
                        concept_ids=[c.concept_id for c in c_grp],
                        learning_objectives=self._collect_objectives(c_grp),
                        prerequisite_lesson_ids=[prev_lid] if prev_lid else [],
                        difficulty=self._max_difficulty(c_grp),
                        estimated_duration_minutes=cur_dur,
                        sequence_index=idx,
                        source_material_ids=[material_id] if material_id else [],
                    )
                )
                prev_lid = cur_lid

        lesson_ids = [l.lesson_id for l in lessons]

        return Syllabus(
            syllabus_id=syllabus_id,
            title=f"{clean_title} ({time} min)",
            description=f"Time-adaptive {desired_depth} curriculum calibrated for {time} minutes.",
            concepts=prioritized,
            lessons=lessons,
            lesson_ids=lesson_ids,
            source_material_ids=[material_id] if material_id else [],
            is_grounded=bool(material_id),
            generation_mode="material_grounded" if material_id else "topic_only",
        )

    # --------------------------------------------------------------------
    # Concept Time-Slice Allocation
    # --------------------------------------------------------------------

    @staticmethod
    def calculate_concept_time_slices(
        concepts: List[str],
        total_time_minutes: int,
    ) -> Dict[str, int]:
        """Distribute total time budget evenly among prioritized concepts."""
        if not concepts:
            return {}

        total_time = max(1, total_time_minutes)
        n = len(concepts)
        base = total_time // n
        remainder = total_time % n

        time_slices: Dict[str, int] = {}
        for i, cid in enumerate(concepts):
            extra = 1 if i < remainder else 0
            time_slices[cid] = max(1, base + extra)

        return time_slices

    # --------------------------------------------------------------------
    # Dynamic Pacing Adaptation
    # --------------------------------------------------------------------

    @staticmethod
    def adapt_pacing(
        remaining_time_minutes: int,
        remaining_concepts_count: int,
        desired_depth: str = "standard",
    ) -> Dict[str, Any]:
        """Dynamically evaluate whether learner is on track, lagging, or ahead of schedule."""
        if remaining_concepts_count <= 0:
            return {
                "status": "completed",
                "recommended_action": "conclude_session",
                "depth_adjustment": desired_depth,
            }

        minutes_per_concept = remaining_time_minutes / remaining_concepts_count

        if minutes_per_concept < 3.0:
            # Running tight on time: suggest condensing explanations and pruning optional details
            return {
                "status": "behind_schedule",
                "recommended_action": "condense_explanations",
                "depth_adjustment": "quick_overview",
                "message": "Pacing alert: Time is running tight. Focusing on high-yield core takeaways.",
            }
        elif minutes_per_concept > 12.0:
            # Ahead of schedule: suggest providing stretch challenge or deeper analogies
            return {
                "status": "ahead_of_schedule",
                "recommended_action": "add_extension_challenge",
                "depth_adjustment": "deep_dive",
                "message": "Pacing note: Excellent progress! We have time for advanced practical applications.",
            }
        else:
            return {
                "status": "on_track",
                "recommended_action": "continue_standard",
                "depth_adjustment": desired_depth,
                "message": "Pacing is optimal.",
            }

    # --------------------------------------------------------------------
    # 7-Day Personalized Learning & Revision Plan
    # --------------------------------------------------------------------

    def generate_seven_day_plan(
        self,
        concept_graph: ConceptGraph,
        topic: str = "Curriculum",
        daily_minutes: int = 30,
        learner_profile: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generate a personalized 7-day learning and spaced-revision schedule.
        
        Each day specifies:
        - concepts to learn or reinforce
        - learning objectives
        - revision requirements (spaced repetition intervals)
        - available time calibration
        - learner mastery grounding
        """
        if not concept_graph or not concept_graph.concepts:
            raise EmptyConceptInputError("Cannot generate 7-day plan from empty concept graph.")

        all_concepts = concept_graph.concepts
        topo_concepts = self._concept_service.topological_sort(
            all_concepts,
            concept_graph.relationships,
        )

        minutes = max(15, min(120, daily_minutes))
        total_concepts = len(topo_concepts)

        # Identify existing weak concepts from learner profile if available
        weak_concept_ids: Set[str] = set()
        mastery_map: Dict[str, float] = {}
        if learner_profile and hasattr(learner_profile, "concept_mastery"):
            for cid, cm in learner_profile.concept_mastery.items():
                score = getattr(cm, "score", 0.0)
                mastery_map[cid] = score
                if score < 0.7:
                    weak_concept_ids.add(cid)

        # Distribute concepts across the week
        # Days 1, 2, 4, 6 focus on new knowledge acquisition
        # Days 3, 5, 7 focus on spaced revision, synthesis, and final assessment
        step = max(1, (total_concepts + 3) // 4)
        c_day1 = topo_concepts[0:step]
        c_day2 = topo_concepts[step:step * 2] if total_concepts > step else topo_concepts[0:1]
        c_day4 = topo_concepts[step * 2:step * 3] if total_concepts > step * 2 else (c_day2 or c_day1)
        c_day6 = topo_concepts[step * 3:] if total_concepts > step * 3 else (c_day4 or c_day2)

        def make_concept_summary(clist: List[Concept]) -> List[Dict[str, Any]]:
            return [
                {
                    "concept_id": c.concept_id,
                    "name": c.name,
                    "difficulty": c.difficulty.value if hasattr(c.difficulty, "value") else str(c.difficulty),
                    "current_mastery": mastery_map.get(c.concept_id, 0.0),
                }
                for c in clist
            ]

        # Prioritize weak concepts for revision slots
        rev_pool_1 = [c for c in c_day1 if c.concept_id in weak_concept_ids] or c_day1[:2]
        rev_pool_2 = [c for c in (c_day1 + c_day2) if c.concept_id in weak_concept_ids] or (c_day2[:2] if c_day2 else c_day1[:2])

        days = [
            {
                "day": 1,
                "title": f"Day 1: Foundations of {topo_concepts[0].name}",
                "focus": "Foundations & Intuition",
                "concepts": make_concept_summary(c_day1),
                "learning_objectives": self._collect_objectives(c_day1),
                "revision_requirements": [],
                "available_time_minutes": minutes,
                "recommended_action": "Complete introduction and foundational interactive demonstrations.",
            },
            {
                "day": 2,
                "title": f"Day 2: Core Mechanics & Dynamics",
                "focus": "Core Principles & Application",
                "concepts": make_concept_summary(c_day2),
                "learning_objectives": self._collect_objectives(c_day2),
                "revision_requirements": [c.name for c in c_day1[:1]],
                "available_time_minutes": minutes,
                "recommended_action": "Connect foundational laws to real-world scenarios and solve guided problems.",
            },
            {
                "day": 3,
                "title": "Day 3: Active Recall & Spaced Revision 1",
                "focus": "Retention Reinforcement",
                "concepts": make_concept_summary(rev_pool_1),
                "learning_objectives": ["Solidify memory traces and resolve early conceptual misconceptions."],
                "revision_requirements": [c.name for c in (c_day1 + c_day2)],
                "available_time_minutes": minutes,
                "recommended_action": "Targeted active-recall practice on foundational and core concepts.",
            },
            {
                "day": 4,
                "title": f"Day 4: Deep Dive & Edge Cases",
                "focus": "Advanced Systems & Edge Cases",
                "concepts": make_concept_summary(c_day4),
                "learning_objectives": self._collect_objectives(c_day4),
                "revision_requirements": [c.name for c in rev_pool_1],
                "available_time_minutes": minutes,
                "recommended_action": "Study multi-concept interactions, edge cases, and mathematical derivations.",
            },
            {
                "day": 5,
                "title": "Day 5: Synthesis & Spaced Revision 2",
                "focus": "Cross-Concept Synthesis",
                "concepts": make_concept_summary(rev_pool_2),
                "learning_objectives": ["Synthesize multi-concept models and test transfer to novel problems."],
                "revision_requirements": [c.name for c in (c_day2 + c_day4)],
                "available_time_minutes": minutes,
                "recommended_action": "Execute transfer questions combining multiple principles simultaneously.",
            },
            {
                "day": 6,
                "title": f"Day 6: Mastery & Technical Applications",
                "focus": "Complex Problem Solving",
                "concepts": make_concept_summary(c_day6),
                "learning_objectives": self._collect_objectives(c_day6),
                "revision_requirements": [c.name for c in c_day4[:1]],
                "available_time_minutes": minutes,
                "recommended_action": "Tackle challenging open-ended questions and examine step-by-step solutions.",
            },
            {
                "day": 7,
                "title": "Day 7: Comprehensive Assessment & Milestone Report",
                "focus": "Evaluation & Next Learning Path",
                "concepts": make_concept_summary(topo_concepts),
                "learning_objectives": ["Benchmark complete curriculum mastery and generate next learning pathway."],
                "revision_requirements": [c.name for c in topo_concepts],
                "available_time_minutes": minutes,
                "recommended_action": "Complete full final assessment, analyze learning report, and plan revision schedule.",
            },
        ]

        return {
            "topic": topic,
            "total_concepts": total_concepts,
            "daily_minutes": minutes,
            "weak_concepts_targeted": list(weak_concept_ids),
            "days": days,
        }

    # --------------------------------------------------------------------
    # Internal Helpers
    # --------------------------------------------------------------------

    @staticmethod
    def _collect_objectives(concepts: List[Concept]) -> List[str]:
        objs: List[str] = []
        for c in concepts:
            for obj in c.learning_objectives:
                if obj not in objs:
                    objs.append(obj)
        return objs

    @staticmethod
    def _max_difficulty(concepts: List[Concept]) -> DifficultyLevel:
        max_rank = max((DIFFICULTY_RANK.get(c.difficulty, 1) for c in concepts), default=1)
        return RANK_TO_DIFFICULTY.get(max_rank, DifficultyLevel.BEGINNER)


time_adaptive_planner = TimeAdaptivePlanner()
