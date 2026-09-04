import hashlib
import logging
import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.exceptions import (
    ConceptCycleError,
    EmptyConceptInputError,
    InvalidConceptError,
    InvalidRelationshipError,
    LLMServiceError,
)
from app.core.gemini import gemini_client
from app.schemas.lesson import (
    Concept,
    ConceptGraph,
    ConceptRelationship,
    ConceptRelationshipType,
    DifficultyLevel,
    RawConceptExtractionResponse,
    RawExtractedConcept,
)
from app.schemas.material import DocumentChunk, ExtractedDocument

logger = logging.getLogger(__name__)

# Bloom's taxonomy measurable action verbs for pedagogical quality validation
BLOOM_ACTION_VERBS = {
    "define", "identify", "describe", "explain", "summarize", "illustrate",
    "apply", "demonstrate", "calculate", "solve", "analyze", "compare",
    "contrast", "evaluate", "formulate", "construct", "trace", "differentiate",
    "classify", "determine", "interpret", "derive", "implement", "assess"
}

# Generic filler patterns to filter out of academic concept extraction
FILLER_PATTERNS = {
    "table of contents", "contents", "index", "introduction", "chapter summary",
    "conclusion", "appendix", "glossary", "preface", "page", "slide",
    "references", "bibliography", "overview", "summary", "notes", "exercises"
}


class ConceptService:
    """Domain service for concept extraction, normalization, and graph operations."""

    def __init__(self, client=None):
        self._gemini_client = client or gemini_client

    # ----------------------------------------------------------------
    # Deterministic Identifiers
    # ----------------------------------------------------------------

    @staticmethod
    def generate_concept_id(name: str, material_id: Optional[str] = None) -> str:
        """Generate a deterministic SHA-256 concept ID from normalized name and material."""
        if not name or not name.strip():
            raise InvalidConceptError("Cannot generate concept ID for empty concept name.")
        norm_name = re.sub(r"\s+", " ", name.strip().lower())
        seed = f"{material_id.strip()}:{norm_name}" if (material_id and material_id.strip()) else norm_name
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"cpt_{digest}"

    # ----------------------------------------------------------------
    # Concept Extraction (Material-Grounded)
    # ----------------------------------------------------------------

    async def extract_concepts_from_document(
        self,
        document: ExtractedDocument,
    ) -> List[Concept]:
        """Extract grounded pedagogical concepts from an ExtractedDocument."""
        if not document or not document.chunks:
            raise EmptyConceptInputError("Cannot extract concepts from an empty document.")
        return await self.extract_concepts_from_chunks(
            chunks=document.chunks,
            material_id=document.material_id,
        )

    async def extract_concepts_from_chunks(
        self,
        chunks: List[DocumentChunk],
        material_id: Optional[str] = None,
    ) -> List[Concept]:
        """Extract grounded pedagogical concepts from a list of DocumentChunks."""
        if not chunks:
            raise EmptyConceptInputError("Cannot extract concepts from an empty chunk list.")

        mat_id = material_id or (chunks[0].material_id if chunks else None)

        # Build grounded context snippet for LLM with explicit chunk IDs
        context_parts = []
        chunk_map: Dict[str, DocumentChunk] = {}
        for chunk in chunks:
            chunk_map[chunk.chunk_id] = chunk
            header = f"[CHUNK_ID: {chunk.chunk_id}]"
            if chunk.chapter:
                header += f" (Chapter: {chunk.chapter})"
            if chunk.section:
                header += f" (Section: {chunk.section})"
            if chunk.page_number is not None:
                header += f" (Page: {chunk.page_number})"
            elif chunk.slide_number is not None:
                header += f" (Slide: {chunk.slide_number})"
            context_parts.append(f"{header}\n{chunk.text}")

        full_context = "\n\n---\n\n".join(context_parts)

        system_instruction = (
            "You are an expert pedagogical concept extractor for an AI Teacher system.\n"
            "Analyze the provided educational text chunks and extract clear, meaningful academic concepts.\n\n"
            "Guidelines:\n"
            "1. Extract core academic and conceptual topics. Avoid filler text, navigation headings, table of contents, and formatting tokens.\n"
            "2. For each concept, provide:\n"
            "   - name: Concise academic name (e.g. 'Binary Search Tree', 'Photosynthesis Light Reactions')\n"
            "   - description: Pedagogical scope and definition grounded in the text\n"
            "   - difficulty: 'beginner', 'intermediate', or 'advanced'\n"
            "   - learning_objectives: 2 to 4 measurable objectives using action verbs (e.g. 'Explain...', 'Apply...', 'Analyze...')\n"
            "   - prerequisite_concept_names: Names of concepts in the material that must be understood first\n"
            "   - related_concept_names: Names of complementary or parallel concepts in the material\n"
            "   - source_chunk_ids: List of exact chunk IDs from which this concept was extracted\n"
            "3. Ground all concepts strictly in the provided material."
        )

        prompt = f"Extract all academic concepts from the following learning material chunks:\n\n{full_context}"

        raw_response = await self._gemini_client.generate_structured(
            prompt=prompt,
            response_schema=RawConceptExtractionResponse,
            system_instruction=system_instruction,
        )

        return self._transform_raw_concepts(
            raw_concepts=raw_response.concepts,
            material_id=mat_id,
            chunk_map=chunk_map,
            is_grounded=True,
        )

    # ----------------------------------------------------------------
    # Concept Extraction (Topic-Only)
    # ----------------------------------------------------------------

    async def extract_concepts_from_topic(
        self,
        topic: str,
    ) -> List[Concept]:
        """Extract pedagogical concepts for a standalone topic without source material grounding."""
        if not topic or not topic.strip():
            raise EmptyConceptInputError("Cannot extract concepts from an empty topic.")

        system_instruction = (
            "You are an expert curriculum designer for an AI Teacher system.\n"
            "Given a subject or topic, decompose it into a structured sequence of academic concepts.\n\n"
            "Guidelines:\n"
            "1. Extract core academic concepts from beginner foundations to advanced applications.\n"
            "2. For each concept, provide:\n"
            "   - name: Concise academic name\n"
            "   - description: Clear pedagogical definition and scope\n"
            "   - difficulty: 'beginner', 'intermediate', or 'advanced'\n"
            "   - learning_objectives: 2 to 4 measurable objectives using Bloom's action verbs\n"
            "   - prerequisite_concept_names: Prerequisites among the extracted concepts\n"
            "   - related_concept_names: Related concepts among the extracted concepts\n"
            "   - source_chunk_ids: MUST BE EMPTY (this is topic-only generation)\n"
            "3. Ensure clean prerequisite progression without circular dependencies."
        )

        prompt = f"Design a comprehensive concept curriculum for the topic: '{topic.strip()}'"

        raw_response = await self._gemini_client.generate_structured(
            prompt=prompt,
            response_schema=RawConceptExtractionResponse,
            system_instruction=system_instruction,
        )

        return self._transform_raw_concepts(
            raw_concepts=raw_response.concepts,
            material_id=None,
            chunk_map={},
            is_grounded=False,
        )

    # ----------------------------------------------------------------
    # Raw Concept Transformation & ID Resolution
    # ----------------------------------------------------------------

    def _transform_raw_concepts(
        self,
        raw_concepts: List[RawExtractedConcept],
        material_id: Optional[str],
        chunk_map: Dict[str, DocumentChunk],
        is_grounded: bool,
    ) -> List[Concept]:
        """Convert raw LLM concepts into validated, normalized Concept objects with deterministic IDs."""
        if not raw_concepts:
            raise EmptyConceptInputError("No concepts were extracted by the model.")

        # 1. Filter out empty/filler concepts
        valid_raw = []
        for rc in raw_concepts:
            clean_name = rc.name.strip()
            if not clean_name:
                continue
            if clean_name.lower() in FILLER_PATTERNS:
                continue
            valid_raw.append(rc)

        if not valid_raw:
            raise EmptyConceptInputError("Extracted concepts only contained filler or invalid items.")

        # 2. Map normalized name to deterministic concept_id
        name_to_id: Dict[str, str] = {}
        for rc in valid_raw:
            norm_key = self._normalize_name_key(rc.name)
            if norm_key not in name_to_id:
                name_to_id[norm_key] = self.generate_concept_id(rc.name, material_id=material_id)

        # 3. Create intermediate Concept objects
        concepts_by_id: Dict[str, Concept] = {}
        for rc in valid_raw:
            norm_key = self._normalize_name_key(rc.name)
            c_id = name_to_id[norm_key]

            # Resolve prerequisite IDs
            prereq_ids = []
            for p_name in rc.prerequisite_concept_names:
                p_key = self._normalize_name_key(p_name)
                if p_key in name_to_id and name_to_id[p_key] != c_id:
                    prereq_id = name_to_id[p_key]
                    if prereq_id not in prereq_ids:
                        prereq_ids.append(prereq_id)

            # Resolve related IDs
            related_ids = []
            for r_name in rc.related_concept_names:
                r_key = self._normalize_name_key(r_name)
                if r_key in name_to_id and name_to_id[r_key] != c_id:
                    rel_id = name_to_id[r_key]
                    if rel_id not in related_ids and rel_id not in prereq_ids:
                        related_ids.append(rel_id)

            # Validate / format learning objectives
            objectives = self._sanitize_learning_objectives(rc.learning_objectives, rc.name)

            # Resolve source chunk IDs and metadata
            source_chunk_ids: List[str] = []
            source_metadata: Dict[str, Any] = {}
            if is_grounded:
                for chk_id in rc.source_chunk_ids:
                    if chk_id in chunk_map:
                        source_chunk_ids.append(chk_id)
                        chunk = chunk_map[chk_id]
                        if "filenames" not in source_metadata:
                            source_metadata["filenames"] = []
                        if chunk.filename not in source_metadata["filenames"]:
                            source_metadata["filenames"].append(chunk.filename)

                # Fallback: if model omitted chunk IDs, ground in all available chunks
                if not source_chunk_ids and chunk_map:
                    source_chunk_ids = list(chunk_map.keys())

            # Difficulty mapping
            diff = self._normalize_difficulty(rc.difficulty)

            if c_id in concepts_by_id:
                # Merge into existing concept
                existing = concepts_by_id[c_id]
                for obj in objectives:
                    if obj not in existing.learning_objectives:
                        existing.learning_objectives.append(obj)
                for pid in prereq_ids:
                    if pid not in existing.prerequisite_concept_ids:
                        existing.prerequisite_concept_ids.append(pid)
                for rid in related_ids:
                    if rid not in existing.related_concept_ids:
                        existing.related_concept_ids.append(rel_id)
                for chkid in source_chunk_ids:
                    if chkid not in existing.source_chunk_ids:
                        existing.source_chunk_ids.append(chkid)
            else:
                concepts_by_id[c_id] = Concept(
                    concept_id=c_id,
                    name=rc.name.strip(),
                    description=rc.description.strip() or f"Core concept: {rc.name.strip()}",
                    difficulty=diff,
                    learning_objectives=objectives,
                    prerequisite_concept_ids=prereq_ids,
                    related_concept_ids=related_ids,
                    source_chunk_ids=source_chunk_ids if is_grounded else [],
                    source_metadata=source_metadata if is_grounded else {},
                )

        normalized_list = list(concepts_by_id.values())
        return self.normalize_concepts(normalized_list)

    # ----------------------------------------------------------------
    # Normalization & Deduplication
    # ----------------------------------------------------------------

    def normalize_concepts(self, concepts: List[Concept]) -> List[Concept]:
        """Normalize concept names, deduplicate concepts, and sanitize relationship references."""
        if not concepts:
            raise EmptyConceptInputError("Cannot normalize an empty list of concepts.")

        concept_map: Dict[str, Concept] = {}
        for c in concepts:
            if not c.name or not c.name.strip():
                raise InvalidConceptError("Concept has missing or empty name.")

            c_id = c.concept_id
            if c_id not in concept_map:
                concept_map[c_id] = c.model_copy(deep=True)
            else:
                # Merge duplicate
                target = concept_map[c_id]
                for obj in c.learning_objectives:
                    if obj not in target.learning_objectives:
                        target.learning_objectives.append(obj)
                for pid in c.prerequisite_concept_ids:
                    if pid not in target.prerequisite_concept_ids and pid != c_id:
                        target.prerequisite_concept_ids.append(pid)
                for rid in c.related_concept_ids:
                    if rid not in target.related_concept_ids and rid != c_id:
                        target.related_concept_ids.append(rid)
                for chk in c.source_chunk_ids:
                    if chk not in target.source_chunk_ids:
                        target.source_chunk_ids.append(chk)
                target.source_metadata.update(c.source_metadata)

        all_ids = set(concept_map.keys())

        # Clean dangling references
        for c in concept_map.values():
            c.prerequisite_concept_ids = [pid for pid in c.prerequisite_concept_ids if pid in all_ids and pid != c.concept_id]
            c.related_concept_ids = [rid for rid in c.related_concept_ids if rid in all_ids and rid != c.concept_id and rid not in c.prerequisite_concept_ids]

        return list(concept_map.values())

    @staticmethod
    def _normalize_name_key(name: str) -> str:
        """Create a normalized lookup key for concept names."""
        return re.sub(r"[^\w\s]", "", name.strip().lower())

    @staticmethod
    def _normalize_difficulty(difficulty: Any) -> DifficultyLevel:
        """Coerce raw difficulty string to DifficultyLevel enum."""
        if isinstance(difficulty, DifficultyLevel):
            return difficulty
        if isinstance(difficulty, str):
            val = difficulty.strip().lower()
            if val in ("beginner", "easy", "introductory", "basic"):
                return DifficultyLevel.BEGINNER
            elif val in ("intermediate", "medium", "moderate"):
                return DifficultyLevel.INTERMEDIATE
            elif val in ("advanced", "hard", "expert", "complex"):
                return DifficultyLevel.ADVANCED
        return DifficultyLevel.BEGINNER

    @staticmethod
    def _sanitize_learning_objectives(objectives: List[str], concept_name: str) -> List[str]:
        """Ensure learning objectives use measurable action verbs and are non-empty."""
        clean_objs = []
        for obj in objectives:
            stripped = obj.strip()
            if stripped and stripped not in clean_objs:
                clean_objs.append(stripped)

        if not clean_objs:
            clean_objs = [
                f"Define the foundational principles of {concept_name}.",
                f"Explain and apply key concepts of {concept_name}.",
            ]
        return clean_objs

    # ----------------------------------------------------------------
    # Graph Construction & Graph Algorithms
    # ----------------------------------------------------------------

    def build_concept_graph(
        self,
        concepts: List[Concept],
        relationships: Optional[List[ConceptRelationship]] = None,
    ) -> ConceptGraph:
        """Build and validate a ConceptGraph data model, checking for invalid references and prerequisite cycles."""
        if not concepts:
            raise EmptyConceptInputError("Cannot build concept graph from empty concepts.")

        concept_ids = {c.concept_id: c for c in concepts}

        built_relationships: List[ConceptRelationship] = []
        seen_rel: Set[Tuple[str, str, str]] = set()

        # If explicit relationships are supplied, validate them
        if relationships is not None:
            for rel in relationships:
                if rel.source_concept_id not in concept_ids:
                    raise InvalidRelationshipError(
                        f"Relationship source concept ID '{rel.source_concept_id}' not found in concepts."
                    )
                if rel.target_concept_id not in concept_ids:
                    raise InvalidRelationshipError(
                        f"Relationship target concept ID '{rel.target_concept_id}' not found in concepts."
                    )
                key = (rel.source_concept_id, rel.target_concept_id, rel.relationship_type.value)
                if key not in seen_rel:
                    seen_rel.add(key)
                    built_relationships.append(rel)
        else:
            # Build relationships from concept prerequisite and related lists
            for c in concepts:
                for prereq_id in c.prerequisite_concept_ids:
                    if prereq_id not in concept_ids:
                        raise InvalidRelationshipError(
                            f"Concept '{c.name}' ({c.concept_id}) references unknown prerequisite '{prereq_id}'."
                        )
                    key = (prereq_id, c.concept_id, ConceptRelationshipType.PREREQUISITE.value)
                    if key not in seen_rel:
                        seen_rel.add(key)
                        built_relationships.append(
                            ConceptRelationship(
                                source_concept_id=prereq_id,
                                target_concept_id=c.concept_id,
                                relationship_type=ConceptRelationshipType.PREREQUISITE,
                            )
                        )
                for rel_id in c.related_concept_ids:
                    if rel_id not in concept_ids:
                        raise InvalidRelationshipError(
                            f"Concept '{c.name}' ({c.concept_id}) references unknown related concept '{rel_id}'."
                        )
                    key = (c.concept_id, rel_id, ConceptRelationshipType.RELATED.value)
                    if key not in seen_rel:
                        seen_rel.add(key)
                        built_relationships.append(
                            ConceptRelationship(
                                source_concept_id=c.concept_id,
                                target_concept_id=rel_id,
                                relationship_type=ConceptRelationshipType.RELATED,
                            )
                        )

        # Validate cycles in prerequisite relationships
        self.detect_cycles(concepts=concepts, relationships=built_relationships)

        return ConceptGraph(
            concepts=concepts,
            relationships=built_relationships,
        )

    def detect_cycles(
        self,
        concepts: List[Concept],
        relationships: List[ConceptRelationship],
    ) -> None:
        """Detect circular prerequisite dependencies using DFS graph traversal and raise ConceptCycleError if found."""
        prereq_adj: Dict[str, List[str]] = defaultdict(list)
        for rel in relationships:
            if rel.relationship_type == ConceptRelationshipType.PREREQUISITE:
                prereq_adj[rel.source_concept_id].append(rel.target_concept_id)

        # 0 = unvisited, 1 = visiting (current path), 2 = visited
        visited: Dict[str, int] = {c.concept_id: 0 for c in concepts}
        path: List[str] = []

        def dfs(node_id: str):
            visited[node_id] = 1
            path.append(node_id)

            for neighbor in prereq_adj.get(node_id, []):
                if visited.get(neighbor, 0) == 1:
                    cycle_start_idx = path.index(neighbor)
                    cycle = path[cycle_start_idx:] + [neighbor]
                    raise ConceptCycleError(
                        f"Circular prerequisite dependency detected: {' -> '.join(cycle)}"
                    )
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)

            path.pop()
            visited[node_id] = 2

        for c in concepts:
            if visited[c.concept_id] == 0:
                dfs(c.concept_id)

    def topological_sort(
        self,
        concepts: List[Concept],
        relationships: Optional[List[ConceptRelationship]] = None,
    ) -> List[Concept]:
        """Compute a deterministic topological sequence of concepts where all prerequisites precede dependents."""
        if not concepts:
            return []

        concept_map = {c.concept_id: c for c in concepts}

        # Validate graph and detect cycles first
        graph = self.build_concept_graph(concepts=concepts, relationships=relationships)

        # Build in-degree and adjacency for prerequisite edges
        in_degree: Dict[str, int] = {c.concept_id: 0 for c in concepts}
        adj: Dict[str, List[str]] = defaultdict(list)

        for rel in graph.relationships:
            if rel.relationship_type == ConceptRelationshipType.PREREQUISITE:
                adj[rel.source_concept_id].append(rel.target_concept_id)
                in_degree[rel.target_concept_id] += 1

        # Deterministic priority queue / sorted list of zero in-degree nodes
        # Sort key: (difficulty priority, concept name, concept_id)
        diff_order = {DifficultyLevel.BEGINNER: 0, DifficultyLevel.INTERMEDIATE: 1, DifficultyLevel.ADVANCED: 2}

        def sort_key(cid: str):
            concept = concept_map[cid]
            return (diff_order.get(concept.difficulty, 0), concept.name.lower(), concept.concept_id)

        zero_in_degree = [cid for cid, deg in in_degree.items() if deg == 0]
        zero_in_degree.sort(key=sort_key)

        queue = deque(zero_in_degree)
        sorted_concepts: List[Concept] = []

        while queue:
            # Re-sort remaining to maintain strict deterministic order on newly freed nodes
            current_available = list(queue)
            current_available.sort(key=sort_key)
            node_id = current_available[0]
            queue = deque(current_available[1:])

            sorted_concepts.append(concept_map[node_id])

            for neighbor in adj[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_concepts) != len(concepts):
            remaining = set(concept_map.keys()) - {c.concept_id for c in sorted_concepts}
            raise ConceptCycleError(f"Prerequisite cycle detected involving concepts: {remaining}")

        return sorted_concepts


# Singleton service instance
concept_service = ConceptService()
