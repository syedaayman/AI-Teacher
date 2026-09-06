"""Video Service module exporting video generator abstractions and service instance."""
from app.services.video_generator import (
    AudioTimingCue,
    VideoGeneratorService,
    VideoManifest,
    VideoScene,
    generate_audio_timing_cues,
    video_generator_service,
)

# Canonical aliases
video_service = video_generator_service

__all__ = [
    "AudioTimingCue",
    "VideoGeneratorService",
    "VideoManifest",
    "VideoScene",
    "generate_audio_timing_cues",
    "video_generator_service",
    "video_service",
]
