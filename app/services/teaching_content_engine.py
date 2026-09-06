import hashlib
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from app.core.gemini import gemini_client
from app.schemas.assessment import Misconception
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import Concept, DifficultyLevel
from app.schemas.material import DocumentChunk
from app.schemas.session import InstructionalDelivery, TeachingStep

logger = logging.getLogger(__name__)


class RawContentPayload(BaseModel):
    """Structured LLM output for pedagogical explanations and demonstrations."""
    title: str = Field(description="Engaging, informative section title")
    content: str = Field(description="Pedagogical narrative in the requested language")
    visual_description: Optional[str] = Field(
        default=None,
        description="Structured blackboard/canvas prompt for Member 2 UI rendering",
    )
    diagram_required: bool = Field(
        default=False,
        description="True if a visual schematic, flowchart, or diagram should be rendered",
    )
    code_snippet: Optional[str] = Field(
        default=None,
        description="Executable code or step-by-step pseudocode/calculation",
    )
    key_takeaways: List[str] = Field(
        default_factory=list,
        description="2 to 4 bullet points summarizing the core principles",
    )
    analogy: Optional[str] = Field(
        default=None,
        description="Intuitive real-world or physical analogy",
    )
    real_world_application: Optional[str] = Field(
        default=None,
        description="Real-world engineering or practical application example",
    )
    counter_example: Optional[str] = Field(
        default=None,
        description="Common trap, counter-example, or edge case",
    )


class TeachingContentEngine:
    """High-fidelity pedagogical content generation engine.
    
    Generates rich, structured instructional deliveries (Explanations, Demonstrations,
    and Remediation) across multiple languages, difficulty levels, and time depths.
    Outputs structured visual cues (`visual_description`, `diagram_required`) for Member 2 UI.
    """

    def __init__(self, client=None):
        self._gemini_client = client or gemini_client

    # --------------------------------------------------------------------
    # Public Generation Interfaces
    # --------------------------------------------------------------------

    async def generate_explanation(
        self,
        concept: Union[Concept, str],
        difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
        language: SupportedLanguage = SupportedLanguage.ENGLISH,
        depth: str = "standard",
        source_chunks: Optional[List[DocumentChunk]] = None,
        concept_id: Optional[str] = None,
    ) -> InstructionalDelivery:
        """Generate conceptual intuition, analogies, mental models, and visual blackboard cues."""
        cid, cname, cdesc = self._resolve_concept_details(concept, concept_id)

        system_instruction = self._build_system_instruction(
            step=TeachingStep.EXPLAIN,
            language=language,
            difficulty=difficulty,
            depth=depth,
        )

        prompt = (
            f"Concept Name: '{cname}'\n"
            f"Description: '{cdesc}'\n"
            f"Target Difficulty: {difficulty.value}\n"
            f"Instructional Depth: {depth}\n"
        )
        if source_chunks:
            grounding_text = "\n---\n".join(chk.text for chk in source_chunks[:3])
            prompt += f"\nSOURCE MATERIAL GROUNDING:\n{grounding_text}\n"

        prompt += (
            "\nDeliver an intuitive, engaging explanation of the concept.\n"
            "Build an intuitive mental model first using a memorable analogy, then detail the mechanism.\n"
            "Include blackboard cues for visual rendering, a real-world application, and key takeaways."
        )

        sources = self._extract_source_citations(source_chunks)
        try:
            raw: RawContentPayload = await self._gemini_client.generate_structured(
                prompt=prompt,
                response_schema=RawContentPayload,
                system_instruction=system_instruction,
            )
            return self._to_delivery(raw, cid, cname, TeachingStep.EXPLAIN, difficulty, language, sources=sources)
        except Exception as ex:
            logger.warning("LLM explanation generation failed, using fallback: %s", ex)
            return self._build_fallback_explanation(cid, cname, difficulty, language, depth, sources=sources)

    async def generate_demonstration(
        self,
        concept: Union[Concept, str],
        difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
        language: SupportedLanguage = SupportedLanguage.ENGLISH,
        depth: str = "standard",
        source_chunks: Optional[List[DocumentChunk]] = None,
        concept_id: Optional[str] = None,
    ) -> InstructionalDelivery:
        """Generate practical demonstration, concrete worked example, code snippet, and state trace."""
        cid, cname, cdesc = self._resolve_concept_details(concept, concept_id)

        system_instruction = self._build_system_instruction(
            step=TeachingStep.DEMONSTRATE,
            language=language,
            difficulty=difficulty,
            depth=depth,
        )

        prompt = (
            f"Concept Name: '{cname}'\n"
            f"Description: '{cdesc}'\n"
            f"Target Difficulty: {difficulty.value}\n"
            f"Instructional Depth: {depth}\n"
        )
        if source_chunks:
            grounding_text = "\n---\n".join(chk.text for chk in source_chunks[:3])
            prompt += f"\nSOURCE MATERIAL GROUNDING:\n{grounding_text}\n"

        prompt += (
            "\nDeliver a concrete, step-by-step practical demonstration of this concept.\n"
            "Walk through an applied scenario or code implementation, explaining intermediate state changes.\n"
            "Include visual blackboard trace notes for Member 2 UI rendering."
        )

        sources = self._extract_source_citations(source_chunks)
        try:
            raw: RawContentPayload = await self._gemini_client.generate_structured(
                prompt=prompt,
                response_schema=RawContentPayload,
                system_instruction=system_instruction,
            )
            return self._to_delivery(raw, cid, cname, TeachingStep.DEMONSTRATE, difficulty, language, sources=sources)
        except Exception as ex:
            logger.warning("LLM demonstration generation failed, using fallback: %s", ex)
            return self._build_fallback_demonstration(cid, cname, difficulty, language, depth, sources=sources)

    async def generate_remediation(
        self,
        concept: Union[Concept, str],
        misconception: Union[Misconception, str],
        difficulty: DifficultyLevel = DifficultyLevel.BEGINNER,
        language: SupportedLanguage = SupportedLanguage.ENGLISH,
        depth: str = "standard",
        concept_id: Optional[str] = None,
        source_chunks: Optional[List[DocumentChunk]] = None,
    ) -> InstructionalDelivery:
        """Generate targeted remediation addressing a diagnosed learner misconception."""
        cid, cname, cdesc = self._resolve_concept_details(concept, concept_id)
        misc_text = misconception.description if isinstance(misconception, Misconception) else str(misconception)

        system_instruction = (
            "You are an empathetic, world-class AI Master Teacher performing targeted remediation.\n"
            f"Language directive: {self._get_language_directive(language)}\n\n"
            "Remediation Strategy:\n"
            "1. Acknowledge why the student's misunderstanding is natural and intuitive.\n"
            "2. Present a clear counter-example demonstrating where that flawed intuition breaks down.\n"
            "3. Contrast the wrong mental model with the correct principle side-by-side.\n"
            "4. Provide a simple clarifying rule or analogy to anchor the correct concept.\n"
            "5. Provide structured blackboard notes (`visual_description`) highlighting the comparison.\n"
        )

        prompt = (
            f"Concept: '{cname}'\n"
            f"Diagnosed Misconception: '{misc_text}'\n"
            f"Target Difficulty: {difficulty.value}\n\n"
            "Deliver a compassionate, highly clarifying remediation explanation addressing this specific flaw."
        )
        if source_chunks:
            grounding_text = "\n---\n".join(chk.text for chk in source_chunks[:3])
            prompt += f"\nSOURCE MATERIAL GROUNDING:\n{grounding_text}\n"

        sources = self._extract_source_citations(source_chunks)
        try:
            raw: RawContentPayload = await self._gemini_client.generate_structured(
                prompt=prompt,
                response_schema=RawContentPayload,
                system_instruction=system_instruction,
            )
            return self._to_delivery(raw, cid, cname, TeachingStep.EXPLAIN, difficulty, language, sources=sources)
        except Exception as ex:
            logger.warning("LLM remediation generation failed, using fallback: %s", ex)
            return self._build_fallback_remediation(cid, cname, misc_text, difficulty, language, sources=sources)

    # --------------------------------------------------------------------
    # Prompt Construction Helpers
    # --------------------------------------------------------------------

    def _build_system_instruction(
        self,
        step: TeachingStep,
        language: SupportedLanguage,
        difficulty: DifficultyLevel,
        depth: str,
    ) -> str:
        lang_dir = self._get_language_directive(language)
        depth_dir = self._get_depth_directive(depth)

        if step == TeachingStep.EXPLAIN:
            focus = (
                "Explain the core intuition and foundational principles of THIS specific concept.\n"
                "- Avoid jumping immediately into dry formulas; build a clear mental model first.\n"
                "- Provide an intuitive physical or real-world analogy relevant to this exact concept.\n"
                "- Describe a visual representation, formula, or diagram for the blackboard (`visual_description`).\n"
                "- Highlight 2 to 4 key takeaways and practical real-world relevance.\n"
                "- IMPORTANT: Do NOT generate programming/Python code for mathematics, physics, biology, or humanities topics.\n"
            )
        else:
            focus = (
                "Provide an applied, step-by-step demonstration of THIS specific concept in action.\n"
                "- CRITICAL DOMAIN SELECTION:\n"
                "  * MATHEMATICS (Percentages, Fractions, Algebra, Calculus, etc.): Provide a concrete worked mathematical problem, step-by-step calculation, and formula application. Leave `code_snippet` NULL.\n"
                "  * SCIENCE (Physics, Chemistry, Biology): Walk through the physical/biological process, formula derivation, or empirical experiment. Leave `code_snippet` NULL unless computational.\n"
                "  * COMPUTER SCIENCE / PROGRAMMING: Walk through an algorithm, data structure trace, or code implementation in `code_snippet`.\n"
                "- Provide blackboard trace notes detailing intermediate states and steps (`visual_description`).\n"
                "- Emphasize why the execution steps produce the expected outcome.\n"
            )

        return (
            "You are a world-class AI Teacher delivering an interactive instructional unit.\n"
            f"Language directive: {lang_dir}\n"
            f"Depth & Time Budget directive: {depth_dir}\n"
            f"Target Difficulty: {difficulty.value}\n\n"
            f"{focus}"
        )

    @staticmethod
    def _get_language_directive(language: SupportedLanguage) -> str:
        if language == SupportedLanguage.HINDI:
            return "Respond entirely in fluent, natural, academic Hindi using Devanagari script."
        elif language == SupportedLanguage.HINGLISH:
            return (
                "Respond in conversational Hinglish (blend of Hindi and English written in Latin script), "
                "as spoken naturally in tech classrooms, tutorials, and universities across India."
            )
        return "Respond entirely in clear, pedagogical, professional English."

    @staticmethod
    def _get_depth_directive(depth: str) -> str:
        if depth == "quick_overview":
            return (
                "Quick Overview Mode (5-minute lesson): Be concise, high-yield, punchy. "
                "Focus strictly on definition, core analogy, and essential takeaways. Keep content under 150 words."
            )
        elif depth == "deep_dive":
            return (
                "Deep Dive Mode (60-minute lesson): Be thorough, comprehensive, and rigorous. "
                "Explore edge cases, internal mechanics, performance trade-offs, and advanced implications."
            )
        return (
            "Standard Mode (20-minute lesson): Balanced pedagogical delivery with full explanation, "
            "concrete example, analogy, and visual blackboard guidance."
        )

    # --------------------------------------------------------------------
    # Resolvers & Schema Converters
    # --------------------------------------------------------------------

    @staticmethod
    def _resolve_concept_details(
        concept: Union[Concept, str],
        concept_id: Optional[str] = None,
    ) -> tuple[str, str, str]:
        if isinstance(concept, Concept):
            return concept.concept_id, concept.name, concept.description
        cname = str(concept).strip()
        cid = concept_id or f"cpt_{hashlib.sha256(cname.lower().encode()).hexdigest()[:12]}"
        return cid, cname, f"Academic concept: {cname}"

    @staticmethod
    def _extract_source_citations(source_chunks: Optional[List[Any]]) -> List[Dict[str, Any]]:
        """Extract structured source citations and page/chapter metadata from retrieved chunks."""
        if not source_chunks:
            return []
        citations = []
        for chk in source_chunks:
            citation = {
                "chunk_id": getattr(chk, "chunk_id", ""),
                "material_id": getattr(chk, "material_id", ""),
                "filename": getattr(chk, "filename", ""),
                "page_number": getattr(chk, "page_number", None),
                "slide_number": getattr(chk, "slide_number", None),
                "chapter": getattr(chk, "chapter", None),
                "section": getattr(chk, "section", None),
            }
            if hasattr(chk, "similarity_score") and chk.similarity_score is not None:
                citation["similarity_score"] = chk.similarity_score
            citations.append(citation)
        return citations

    @staticmethod
    def _to_delivery(
        raw: RawContentPayload,
        concept_id: str,
        concept_name: str,
        step: TeachingStep,
        difficulty: DifficultyLevel,
        language: SupportedLanguage,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> InstructionalDelivery:
        return InstructionalDelivery(
            step=step,
            concept_id=concept_id,
            concept_name=concept_name,
            title=raw.title,
            content=raw.content,
            visual_description=raw.visual_description,
            diagram_required=raw.diagram_required,
            code_snippet=raw.code_snippet,
            key_takeaways=raw.key_takeaways,
            analogy=raw.analogy,
            real_world_application=raw.real_world_application,
            counter_example=raw.counter_example,
            language=language,
            difficulty=difficulty,
            sources=sources or [],
        )

    # --------------------------------------------------------------------
    # Deterministic Fallback Generators (Offline / Unit Tests)
    # --------------------------------------------------------------------

    def _build_fallback_explanation(
        self,
        concept_id: str,
        concept_name: str,
        difficulty: DifficultyLevel,
        language: SupportedLanguage,
        depth: str,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> InstructionalDelivery:
        if language == SupportedLanguage.HINDI:
            title = f"{concept_name} की मूल अवधारणा"
            content = f"{concept_name} को समझना अत्यंत महत्वपूर्ण है। यह प्रणाली को व्यवस्थित रूप से कार्य करने में सक्षम बनाता है।"
            analogy = f"{concept_name} एक सुव्यवस्थित पुस्तकालय की तरह है।"
        elif language == SupportedLanguage.HINGLISH:
            title = f"{concept_name} Ka Conceptual Overview"
            content = f"Chaliye samajhte hain {concept_name} kaise kaam karta hai. Ye ek essential concept hai jo system efficiency provide karta hai."
            analogy = f"Isko aap ek organized library ke shelf index ki tarah imagine kar sakte hain."
        else:
            title = f"Foundations of {concept_name}"
            content = (
                f"Welcome to our study of {concept_name}. At the {difficulty.value} level, "
                f"understanding how this mechanism functions is foundational. It organizes components systematically "
                f"to ensure reliable performance."
            )
            analogy = f"Think of {concept_name} like an indexed directory cataloging resources for instant lookup."

        return InstructionalDelivery(
            step=TeachingStep.EXPLAIN,
            concept_id=concept_id,
            concept_name=concept_name,
            title=title,
            content=content,
            visual_description=f"Architecture diagram showing {concept_name} component interaction and data flow.",
            diagram_required=True,
            analogy=analogy,
            real_world_application=f"Widely applied in production systems to optimize {concept_name} throughput.",
            counter_example=f"Assuming {concept_name} can operate without resource limits causes bottlenecking.",
            key_takeaways=[
                f"Core mechanism of {concept_name}",
                f"Calibrated for {difficulty.value} level",
                f"Optimized for {depth} depth",
            ],
            language=language,
            difficulty=difficulty,
            sources=sources or [],
        )

    def _build_fallback_demonstration(
        self,
        concept_id: str,
        concept_name: str,
        difficulty: DifficultyLevel,
        language: SupportedLanguage,
        depth: str,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> InstructionalDelivery:
        if language == SupportedLanguage.HINDI:
            title = f"{concept_name} का व्यावहारिक उदाहरण"
            content = f"आइए {concept_name} के चरणबद्ध क्रियान्वयन को कोड और ट्रेस के माध्यम से देखें।"
        elif language == SupportedLanguage.HINGLISH:
            title = f"{concept_name} In Action: Step-by-Step Demo"
            content = f"Ab hum dekhte hain ki code me {concept_name} step-by-step kaise execute hota hai."
        else:
            title = f"Demonstration: {concept_name} in Action"
            content = (
                f"Let us walk through an applied demonstration of {concept_name}. "
                f"Observe how inputs pass through the logic pipeline to generate verified outputs."
            )

        is_programming = any(
            k in concept_name.lower()
            for k in [
                "code", "program", "python", "java", "sql", "tree", "array",
                "graph", "sort", "algorithm", "data structure", "api", "function",
                "variable", "loop", "recursion", "pointer", "pointers", "memory",
                "stack", "queue", "heap", "linked list", "hash", "class", "object",
                "method", "binary", "byte", "debug"
            ]
        )
        code = (
            f"# Demonstration: {concept_name}\n"
            f"def execute_{concept_id[:8]}(data):\n"
            f"    # Process data according to {concept_name} principles\n"
            f"    return [item for item in data if item is not None]\n"
        ) if is_programming else None

        visual_desc = (
            f"Step-by-step state chart illustrating {concept_name} execution pipeline."
            if is_programming
            else f"Step-by-step demonstration breakdown and worked calculation for {concept_name}."
        )

        return InstructionalDelivery(
            step=TeachingStep.DEMONSTRATE,
            concept_id=concept_id,
            concept_name=concept_name,
            title=title,
            content=content,
            visual_description=visual_desc,
            diagram_required=True,
            code_snippet=code,
            key_takeaways=[
                f"Execution trace of {concept_name}",
                "State transitions preserve correctness invariants",
            ],
            language=language,
            difficulty=difficulty,
            sources=sources or [],
        )

    def _build_fallback_remediation(
        self,
        concept_id: str,
        concept_name: str,
        misconception_text: str,
        difficulty: DifficultyLevel,
        language: SupportedLanguage,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> InstructionalDelivery:
        if language == SupportedLanguage.HINDI:
            title = f"{concept_name} का निवारण और स्पष्टीकरण"
            content = f"यह सोचना स्वाभाविक है कि '{misconception_text}', लेकिन वास्तव में यह नियम हमेशा लागू नहीं होता।"
        elif language == SupportedLanguage.HINGLISH:
            title = f"Clarifying {concept_name}: Common Trap"
            content = f"Ye sochna understandable hai ki '{misconception_text}', lekin practically ye assumptions fail ho jati hain."
        else:
            title = f"Targeted Remediation: Clarifying {concept_name}"
            content = (
                f"It is a very common intuition to believe that '{misconception_text}'. However, "
                f"in practice, this assumption breaks down under boundary conditions. Let's contrast "
                f"the flawed intuition with the true principle."
            )

        return InstructionalDelivery(
            step=TeachingStep.EXPLAIN,
            concept_id=concept_id,
            concept_name=concept_name,
            title=title,
            content=content,
            visual_description=f"Side-by-side comparison: Flawed Intuition vs Correct Principle for {concept_name}.",
            diagram_required=True,
            counter_example=f"Demonstrating failure case when assuming: {misconception_text}",
            key_takeaways=[
                f"Address misconception: {misconception_text}",
                f"Re-anchor {concept_name} foundations",
            ],
            language=language,
            difficulty=difficulty,
            sources=sources or [],
        )



teaching_content_engine = TeachingContentEngine()
