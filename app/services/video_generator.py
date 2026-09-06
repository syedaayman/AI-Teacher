import os
import re
import hashlib
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AudioTimingCue(BaseModel):
    """Pre-rendered audio and visual timing cue for synchronizing avatar gestures, subtitles, and stage cues."""
    cue_id: str = Field(description="Unique cue identifier")
    scene_id: Optional[str] = Field(default=None, description="Associated scene identifier")
    start_time: float = Field(description="Start offset in seconds")
    end_time: float = Field(description="End offset in seconds")
    duration: float = Field(description="Duration of this cue in seconds")
    text: str = Field(description="Spoken narration phrase or subtitle")
    avatar_state: str = Field(
        default="SPEAKING",
        description="Avatar visual posture: IDLE | SPEAKING | THINKING | LISTENING | ENCOURAGING"
    )
    emphasis: Optional[str] = Field(
        default=None,
        description="Pedagogical concept or keyword emphasized in this phrase"
    )


class VideoScene(BaseModel):
    scene_id: str
    scene_type: str = Field(description="intro | explanation | visual | demonstration | key_takeaway | question")
    title: str
    avatar_state: str = Field(description="IDLE | SPEAKING | THINKING | LISTENING | ENCOURAGING")
    narration_text: str
    visual_elements: Dict[str, Any] = Field(default_factory=dict)
    duration_seconds: float = Field(default=8.0)
    timing_cues: List[AudioTimingCue] = Field(
        default_factory=list,
        description="Pre-rendered audio timing cues for this scene"
    )


class VideoManifest(BaseModel):
    video_id: str
    topic: str
    concept_id: Optional[str] = None
    concept_name: str
    total_duration_seconds: float
    scenes: List[VideoScene]
    status: str = "planned"
    provider: str = Field(
        default="local_canvas",
        description="Active video generator engine: 'local_canvas', 'heygen', or 'did'"
    )
    playable_format: str = "video/webm"
    video_url: Optional[str] = None
    timing_cues: List[AudioTimingCue] = Field(
        default_factory=list,
        description="Aggregated pre-rendered audio timing cues across all scenes for the frontend TeacherStage"
    )
    external_dependency_notice: Optional[str] = None


def generate_audio_timing_cues(
    scene_id: str,
    narration_text: str,
    scene_duration: float,
    avatar_state: str,
    concept_name: str,
    start_offset: float = 0.0,
) -> List[AudioTimingCue]:
    """Calculate pre-rendered audio timing cues for synchronized frontend TeacherStage playback."""
    clean_text = (narration_text or "").strip()
    if not clean_text:
        clean_text = f"Exploring {concept_name}."

    # Split into sentence/phrase chunks using punctuation boundaries
    raw_phrases = [p.strip() for p in re.split(r"(?<=[.?!;:])\s+", clean_text) if p.strip()]
    if not raw_phrases:
        raw_phrases = [clean_text]

    total_chars = sum(len(p) for p in raw_phrases) or 1
    cues: List[AudioTimingCue] = []
    current_time = start_offset

    for idx, phrase in enumerate(raw_phrases):
        weight = len(phrase) / total_chars
        cue_duration = max(1.0, round(scene_duration * weight, 2))

        if idx == len(raw_phrases) - 1:
            end_time = round(start_offset + scene_duration, 2)
            cue_duration = max(0.5, round(end_time - current_time, 2))
        else:
            end_time = round(current_time + cue_duration, 2)

        has_emphasis = concept_name.lower() in phrase.lower()

        cues.append(
            AudioTimingCue(
                cue_id=f"{scene_id}_cue_{idx + 1}",
                scene_id=scene_id,
                start_time=round(current_time, 2),
                end_time=round(end_time, 2),
                duration=round(cue_duration, 2),
                text=phrase,
                avatar_state=avatar_state,
                emphasis=concept_name if has_emphasis else None,
            )
        )
        current_time = end_time

    return cues


class VideoGeneratorService:
    """Service for composing and generating structured AI Teaching Videos.

    Adheres to Hackathon Specifications:
    - Structured configuration checks for HEYGEN_API_KEY and DID_API_KEY
    - Automatic graceful fallback to 'local_canvas' provider when external keys are missing
    - Pre-rendered audio timing cues for synchronized frontend TeacherStage rendering
    """

    def __init__(self):
        self.heygen_api_key = os.getenv("HEYGEN_API_KEY")
        self.did_api_key = os.getenv("DID_API_KEY")

    def check_configuration(self) -> Dict[str, Any]:
        """Perform structured configuration check for external AI video providers."""
        heygen_ready = bool(self.heygen_api_key and self.heygen_api_key.strip())
        did_ready = bool(self.did_api_key and self.did_api_key.strip())

        active = "heygen" if heygen_ready else ("did" if did_ready else "local_canvas")

        return {
            "active_provider": active,
            "provider": active,
            "external_keys_configured": heygen_ready or did_ready,
            "configuration_check": {
                "HEYGEN_API_KEY": {
                    "configured": heygen_ready,
                    "status": "ready" if heygen_ready else "missing",
                    "engine": "HeyGen Photorealistic AI Avatar Engine",
                },
                "DID_API_KEY": {
                    "configured": did_ready,
                    "status": "ready" if did_ready else "missing",
                    "engine": "D-ID Real-Time Video Engine",
                },
            },
            "local_canvas_ready": True,
            "notice": (
                "External video generation credentials (HEYGEN_API_KEY, DID_API_KEY) are missing. "
                "Active mode is 'local_canvas' with pre-rendered audio timing cues."
                if not (heygen_ready or did_ready)
                else f"Using configured external video provider: {active}"
            ),
        }

    def get_provider_status(self) -> Dict[str, Any]:
        """Report available video engines and structured external credentials check."""
        cfg = self.check_configuration()
        heygen_ready = cfg["configuration_check"]["HEYGEN_API_KEY"]["configured"]
        did_ready = cfg["configuration_check"]["DID_API_KEY"]["configured"]

        providers = [
            {
                "id": "local_canvas_composer",
                "alias": "local_canvas",
                "name": "Local High-Definition Canvas Video Engine",
                "status": "available",
                "is_active": not (heygen_ready or did_ready),
                "description": "Composites avatar, blackboard notes, live captions, and SVG diagrams into high-quality WebM video.",
                "supported_formats": ["video/webm", "video/mp4"],
                "requires_api_key": False,
            },
            {
                "id": "heygen",
                "name": "HeyGen Photorealistic AI Avatar Engine",
                "status": "available" if heygen_ready else "missing_credentials",
                "is_active": heygen_ready,
                "description": "Photorealistic lip-synced video generation API.",
                "supported_formats": ["video/mp4"],
                "requires_api_key": True,
                "env_variable": "HEYGEN_API_KEY",
                "configured": heygen_ready,
            },
            {
                "id": "did",
                "name": "D-ID Real-Time Video Engine",
                "status": "available" if did_ready else "missing_credentials",
                "is_active": not heygen_ready and did_ready,
                "description": "Real-time interactive talking head avatar video generator.",
                "supported_formats": ["video/mp4"],
                "requires_api_key": True,
                "env_variable": "DID_API_KEY",
                "configured": did_ready,
            },
        ]

        return {
            "active_provider": cfg["active_provider"],
            "provider": cfg["provider"],
            "configuration_check": cfg["configuration_check"],
            "providers": providers,
            "notice": cfg["notice"],
        }

    def plan_lesson_video_scenes(
        self,
        topic: str,
        concept_name: str,
        concept_id: Optional[str] = None,
        delivery_content: Optional[str] = None,
        language: str = "english",
    ) -> VideoManifest:
        """Compose progressive teaching scenes with pre-rendered audio timing cues."""
        cid = concept_id or f"c_{hashlib.md5(concept_name.encode()).hexdigest()[:8]}"
        vid_seed = f"{topic}:{concept_name}:{language}:{cid}"
        vid_id = f"vid_{hashlib.sha256(vid_seed.encode()).hexdigest()[:14]}"

        # Clean teacher dialogue content or construct intuitive default
        content = (delivery_content or "").strip()
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()] if content else []
        main_explanation = paragraphs[0] if paragraphs else f"Welcome to our study of {concept_name}. Today we will explore how this principle governs {topic}."
        second_point = paragraphs[1] if len(paragraphs) > 1 else f"To understand {concept_name}, notice the direct cause-and-effect relationship in physical systems."

        raw_scenes = [
            # Scene 1: Introduction
            {
                "type": "intro",
                "title": f"Introduction to {concept_name}",
                "state": "SPEAKING",
                "text": f"Hello! I am your AI Teacher. Let us begin our lesson on {concept_name} in {topic}.",
                "visuals": {
                    "stage_title": f"Lesson: {concept_name}",
                    "subtitle": topic,
                    "badge": "Classroom Stage",
                },
                "duration": 6.0,
            },
            # Scene 2: Foundational Explanation
            {
                "type": "explanation",
                "title": "Foundational Explanation",
                "state": "SPEAKING",
                "text": main_explanation,
                "visuals": {
                    "blackboard_notes": [
                        f"Core Subject: {concept_name}",
                        "Fundamental Law / Definition",
                        "Key Governing Variable",
                    ],
                    "highlight": concept_name,
                },
                "duration": 10.0,
            },
            # Scene 3: Visual Demonstration
            {
                "type": "visual",
                "title": f"Visual Demonstration: {concept_name}",
                "state": "THINKING",
                "text": "Take a look at this visual representation. Observe how each element connects to our core principle.",
                "visuals": {
                    "diagram_title": f"{concept_name} Diagram",
                    "diagram_type": "concept_flow",
                    "cards": ["Input System", "Process Transformation", "Observed Outcome"],
                },
                "duration": 8.0,
            },
            # Scene 4: Practical Demonstration
            {
                "type": "demonstration",
                "title": "Applied Demonstration",
                "state": "SPEAKING",
                "text": second_point,
                "visuals": {
                    "steps": [
                        "Step 1: Identify initial state and forces/inputs",
                        "Step 2: Apply the governing formula or rule",
                        "Step 3: Analyze the resulting equilibrium or output",
                    ],
                },
                "duration": 10.0,
            },
            # Scene 5: Key Takeaway
            {
                "type": "key_takeaway",
                "title": "Key Takeaways",
                "state": "ENCOURAGING",
                "text": f"Remember the key takeaway: {concept_name} provides the foundation for our next concepts.",
                "visuals": {
                    "summary_bullets": [
                        f"1. {concept_name} is universally consistent.",
                        "2. Always verify boundary conditions and assumptions.",
                        "3. Ready for interactive verification.",
                    ],
                },
                "duration": 7.0,
            },
            # Scene 6: Interactive Question Checkpoint
            {
                "type": "question",
                "title": "Understanding Checkpoint",
                "state": "LISTENING",
                "text": "Now let's check your understanding. Consider this question carefully.",
                "visuals": {
                    "checkpoint_prompt": f"How would you explain the core mechanism of {concept_name}?",
                },
                "duration": 6.0,
            },
        ]

        scenes: List[VideoScene] = []
        all_timing_cues: List[AudioTimingCue] = []
        cumulative_time = 0.0

        for idx, rs in enumerate(raw_scenes):
            s_id = f"{vid_id}_s{idx + 1}"
            s_duration = rs["duration"]
            s_state = rs["state"]
            s_text = rs["text"]

            # Compute pre-rendered audio timing cues for this scene
            scene_cues = generate_audio_timing_cues(
                scene_id=s_id,
                narration_text=s_text,
                scene_duration=s_duration,
                avatar_state=s_state,
                concept_name=concept_name,
                start_offset=cumulative_time,
            )

            scenes.append(
                VideoScene(
                    scene_id=s_id,
                    scene_type=rs["type"],
                    title=rs["title"],
                    avatar_state=s_state,
                    narration_text=s_text,
                    visual_elements=rs["visuals"],
                    duration_seconds=s_duration,
                    timing_cues=scene_cues,
                )
            )

            all_timing_cues.extend(scene_cues)
            cumulative_time += s_duration

        total_duration = round(cumulative_time, 2)

        # Check external credentials
        heygen_ready = bool(self.heygen_api_key and self.heygen_api_key.strip())
        did_ready = bool(self.did_api_key and self.did_api_key.strip())

        active_provider = "heygen" if heygen_ready else ("did" if did_ready else "local_canvas")

        external_notice = None
        if not heygen_ready and not did_ready:
            external_notice = (
                "External photorealistic avatar providers (HeyGen/D-ID) require API keys in environment. "
                "Rendering locally via High-Definition Canvas Video Engine with pre-rendered audio timing cues."
            )

        return VideoManifest(
            video_id=vid_id,
            topic=topic,
            concept_id=cid,
            concept_name=concept_name,
            total_duration_seconds=total_duration,
            scenes=scenes,
            status="planned",
            provider=active_provider,
            playable_format="video/webm",
            timing_cues=all_timing_cues,
            external_dependency_notice=external_notice,
        )


video_generator_service = VideoGeneratorService()
