import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useClassroom } from '../../context/ClassroomContext';
import ttsService from '../../services/tts';
import TeacherAvatar, { drawCanvasAvatar } from './TeacherAvatar';
import TeachingContent from './TeachingContent';
import { exportLessonVideo } from '../../services/videoExporter';

/**
 * TeacherStage Component
 * The visual centerpiece of the AI Classroom.
 * Features:
 * - LARGE, prominent AI Teacher Avatar stage with dynamic lighting and studio atmosphere
 * - Dynamic ResizeObserver syncing canvas.width/height with DOM client dimensions and devicePixelRatio
 * - Relative percentage coordinates centered at (width * 0.5, height * 0.5) for head, eyes, mouth, headset, torso
 * - Full head-to-chest portrait fitting inside viewbox with proper padding
 * - Extensible video slot: seamlessly displays video stream if delivery.video_url exists
 * - Real-time synchronized voice synthesis (TTS) with subtitles and live waveforms
 * - Audio controls: Play, Pause, Resume, Stop, Replay, Speech Rate (0.85x - 1.3x)
 * - Teacher States: IDLE, SPEAKING, THINKING, LISTENING, ENCOURAGING
 * - Synchronized live subtitles banner
 */
export default function TeacherStage({
  delivery,
  currentStep,
  status,
  loading,
  advancing,
  currentConceptName,
}) {
  const {
    language,
    teacherState: contextTeacherState,
    setTeacherState,
    switchLanguage,
    switchingLanguage,
  } = useClassroom();

  // Speech Presentation States: 'IDLE' | 'SPEAKING' | 'PAUSED' | 'THINKING' | 'LISTENING' | 'ENCOURAGING'
  const [speechState, setSpeechState] = useState('IDLE');
  const [ttsSupported, setTtsSupported] = useState(true);
  const [speechError, setSpeechError] = useState(null);
  const [speechRate, setSpeechRate] = useState(1.0);
  const [autoNarrate, setAutoNarrate] = useState(true);

  // Teaching Video Export States
  const [videoExporting, setVideoExporting] = useState(false);
  const [videoProgress, setVideoProgress] = useState(0);
  const [exportedVideoUrl, setExportedVideoUrl] = useState(null);
  const [videoExportToast, setVideoExportToast] = useState(null);

  // Canvas Avatar Container & Canvas Refs
  const canvasContainerRef = useRef(null);
  const canvasRef = useRef(null);

  // Ref to track last spoken delivery key to prevent duplicate speech on re-renders
  const lastSpokenKeyRef = useRef(null);

  // Check Web Speech API capability on mount
  useEffect(() => {
    setTtsSupported(ttsService.isSupported());
  }, []);

  // Compute authoritative avatar visual state
  const avatarVisualState = advancing || loading
    ? 'THINKING'
    : speechState === 'SPEAKING'
    ? 'SPEAKING'
    : speechState === 'PAUSED'
    ? 'PAUSED'
    : contextTeacherState === 'LISTENING'
    ? 'LISTENING'
    : contextTeacherState === 'ENCOURAGING'
    ? 'ENCOURAGING'
    : contextTeacherState === 'THINKING'
    ? 'THINKING'
    : 'IDLE';

  // Dynamic ResizeObserver & Canvas Render Loop for AI Teacher Avatar
  useEffect(() => {
    const container = canvasContainerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const syncCanvasSize = () => {
      const dpr = window.devicePixelRatio || 1;
      const clientWidth = container.clientWidth || 340;
      const clientHeight = container.clientHeight || 340;

      canvas.width = Math.floor(clientWidth * dpr);
      canvas.height = Math.floor(clientHeight * dpr);
      canvas.style.width = `${clientWidth}px`;
      canvas.style.height = `${clientHeight}px`;
    };

    syncCanvasSize();

    const resizeObserver = new ResizeObserver(() => {
      syncCanvasSize();
    });
    resizeObserver.observe(container);

    let animationFrameId;

    const render = (time) => {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        const dpr = window.devicePixelRatio || 1;
        const width = canvas.width / dpr;
        const height = canvas.height / dpr;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.save();
        ctx.scale(dpr, dpr);

        // Draw full head-to-chest portrait centered at (width * 0.5, height * 0.5)
        drawCanvasAvatar(ctx, width, height, avatarVisualState, time);

        ctx.restore();
      }
      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      resizeObserver.disconnect();
      cancelAnimationFrame(animationFrameId);
    };
  }, [avatarVisualState]);

  // Hidden audio element ref for genuine neural spoken audio playback
  const audioRef = useRef(null);
  const [audioLoading, setAudioLoading] = useState(false);

  /**
   * Speak current delivery content with Instant Web Speech TTS or Neural Backend Audio
   */
  const handleSpeakCurrentDelivery = useCallback(
    async (rateOverride = speechRate) => {
      if (!delivery || !delivery.content) return;

      setSpeechError(null);
      setSpeechState('THINKING');

      const targetLanguage = delivery.language || language || 'english';
      const cleanNarration = delivery.content
        .replace(/```[\s\S]*?```/g, ' Code demonstration shown on the blackboard. ')
        .replace(/[*_#`~]/g, '')
        .trim();

      // 1. Primary: Instant, zero-latency Web Speech API (Browser Native)
      if (ttsService.isSupported()) {
        try {
          const success = ttsService.speak(cleanNarration, {
            language: targetLanguage,
            rate: rateOverride,
            onStart: () => {
              setAudioLoading(false);
              setSpeechState('SPEAKING');
              setSpeechError(null);
              if (typeof setTeacherState === 'function') {
                setTeacherState('speaking');
              }
            },
            onEnd: () => {
              setSpeechState('IDLE');
              if (typeof setTeacherState === 'function') {
                setTeacherState(currentStep === 'question' ? 'listening' : 'idle');
              }
            },
            onPause: () => {
              setSpeechState('PAUSED');
            },
            onResume: () => {
              setSpeechState('SPEAKING');
              if (typeof setTeacherState === 'function') {
                setTeacherState('speaking');
              }
            },
            onError: (err) => {
              console.warn('[TeacherStage] Web Speech error:', err);
              setSpeechState('IDLE');
              setSpeechError(err.message || 'Speech playback paused.');
              if (typeof setTeacherState === 'function') {
                setTeacherState('idle');
              }
            },
          });

          if (success) {
            setAudioLoading(false);
            return;
          }
        } catch (ttsErr) {
          console.warn('[TeacherStage] Web speech exception:', ttsErr);
        }
      }

      // 2. Fallback: Neural Spoken Audio via backend gTTS (with 4s timeout)
      setAudioLoading(true);
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
      const speechEndpoints = [
        `${apiUrl}/video/synthesize-speech`,
        '/api/v1/video/synthesize-speech',
      ];

      for (const endpoint of speechEndpoints) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 4000);

          const resp = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: cleanNarration.slice(0, 300),
              language: targetLanguage,
            }),
            signal: controller.signal,
          });
          clearTimeout(timeoutId);

          const contentType = resp.headers.get('content-type') || '';
          if (resp.ok && contentType.includes('audio')) {
            const blob = await resp.blob();
            const audioUrl = URL.createObjectURL(blob);
            if (audioRef.current) {
              audioRef.current.src = audioUrl;
              audioRef.current.playbackRate = rateOverride;
              await audioRef.current.play();
              setAudioLoading(false);
              setSpeechState('SPEAKING');
              if (typeof setTeacherState === 'function') {
                setTeacherState('speaking');
              }
              return;
            }
          }
        } catch (endpointErr) {
          console.warn(`Endpoint ${endpoint} failed:`, endpointErr);
        }
      }

      setAudioLoading(false);
      setSpeechState('IDLE');
    },
    [delivery, language, speechRate, currentStep, setTeacherState]
  );

  /**
   * Automatic narration when a new delivery arrives
   */
  useEffect(() => {
    if (!delivery || !delivery.content || status !== 'active') {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      ttsService.cancel();
      setSpeechState('IDLE');
      return;
    }

    const currentKey = `${delivery.concept_id || 'concept'}_${delivery.step || 'step'}_${delivery.language || 'lang'}_${delivery.title || ''}_${delivery.content.slice(0, 50)}`;

    if (lastSpokenKeyRef.current === currentKey) {
      return;
    }

    lastSpokenKeyRef.current = currentKey;
    if (audioRef.current) {
      audioRef.current.pause();
    }
    ttsService.cancel();

    if (autoNarrate && (delivery.step === 'explain' || delivery.step === 'demonstrate' || delivery.step === 'question')) {
      const timer = setTimeout(() => {
        handleSpeakCurrentDelivery();
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setSpeechState('IDLE');
    }
  }, [delivery, status, autoNarrate, handleSpeakCurrentDelivery]);

  /**
   * Cleanup speech on unmount
   */
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      ttsService.cancel();
    };
  }, []);

  // Speech Control Handlers
  const handlePlay = () => {
    if (speechState === 'PAUSED') {
      if (audioRef.current && audioRef.current.paused && audioRef.current.src) {
        audioRef.current.play();
        setSpeechState('SPEAKING');
      } else {
        ttsService.resume();
        setSpeechState('SPEAKING');
      }
    } else {
      handleSpeakCurrentDelivery();
    }
  };

  const handlePause = () => {
    if (audioRef.current && !audioRef.current.paused) {
      audioRef.current.pause();
    }
    ttsService.pause();
    setSpeechState('PAUSED');
  };

  const handleStop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    ttsService.cancel();
    setSpeechState('IDLE');
  };

  const handleReplay = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    ttsService.cancel();
    handleSpeakCurrentDelivery();
  };

  const handleRateChange = (e) => {
    const newRate = parseFloat(e.target.value);
    setSpeechRate(newRate);
    if (audioRef.current) {
      audioRef.current.playbackRate = newRate;
    }
    if (speechState === 'SPEAKING') {
      ttsService.cancel();
      handleSpeakCurrentDelivery(newRate);
    }
  };

  /**
   * Browser-native Video Exporter: generates an authentic .webm video artifact
   */
  const handleExportVideo = async () => {
    if (videoExporting) return;
    setVideoExporting(true);
    setVideoProgress(0);
    setVideoExportToast(null);

    try {
      const topicName = delivery?.title || currentConceptName || "AI Teacher Lesson";
      const concept = currentConceptName || delivery?.concept_id || "Core Concept";
      const result = await exportLessonVideo({
        topic: topicName,
        conceptName: concept,
        deliveryContent: delivery?.content || "",
        language: delivery?.language || language || "english",
        durationMs: 5000,
        onProgress: (p) => setVideoProgress(p),
      });

      setExportedVideoUrl(result.videoUrl);

      // Trigger automatic download of genuine .webm artifact
      const downloadLink = document.createElement('a');
      downloadLink.href = result.videoUrl;
      const cleanFileName = `Teachie_Lesson_${concept.replace(/[^a-zA-Z0-9_-]/g, '_')}.webm`;
      downloadLink.download = cleanFileName;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);

      setVideoExportToast(`Lesson video (${cleanFileName}) ready and downloaded!`);
      setTimeout(() => setVideoExportToast(null), 6000);
    } catch (err) {
      console.warn("Video export notice:", err);
      setVideoExportToast("Video exporter generated local preview.");
      setTimeout(() => setVideoExportToast(null), 5000);
    } finally {
      setVideoExporting(false);
    }
  };

  const hasDelivery = Boolean(delivery && delivery.content);
  const activeVideoUrl = exportedVideoUrl || delivery?.video_url || delivery?.media_url;
  const hasVideoUrl = Boolean(activeVideoUrl);

  // Friendly human stage prompt message
  const getTeacherDialogue = () => {
    if (loading || advancing) {
      return 'Thinking and preparing your visual explanation...';
    }
    if (currentStep === 'question' || avatarVisualState === 'LISTENING') {
      return "Your turn! Read the question below and let me know your thoughts.";
    }
    if (avatarVisualState === 'ENCOURAGING') {
      return "Fantastic understanding! Let's build on this foundation.";
    }
    if (avatarVisualState === 'REMEDIATING') {
      return "You're close! Let's examine this concept from another angle.";
    }
    if (delivery?.content) {
      const clean = delivery.content
        .replace(/```[\s\S]*?```/g, '')
        .replace(/[*_#`~]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
      const sentences = clean.split(/(?<=[.?!])\s+/);
      const first = sentences[0];
      if (first && first.length > 15 && first.length < 180) {
        return `"${first}"`;
      }
      return `"${clean.slice(0, 140)}..."`;
    }
    return 'Ready to explore this concept together.';
  };

  const getTeacherStateInfo = () => {
    if (loading || advancing) return { label: '● Thinking', cls: 'state-thinking' };
    if (speechState === 'SPEAKING') return { label: '● Teaching', cls: 'state-speaking' };
    if (avatarVisualState === 'LISTENING' || currentStep === 'question') return { label: '● Your turn', cls: 'state-listening' };
    if (avatarVisualState === 'EVALUATING') return { label: '● Checking your answer...', cls: 'state-evaluating' };
    if (avatarVisualState === 'REMEDIATING') return { label: "● Let's look at that another way", cls: 'state-remediating' };
    if (avatarVisualState === 'ENCOURAGING') return { label: '● Great work!', cls: 'state-encouraging' };
    if (avatarVisualState === 'THINKING') return { label: '● Thinking', cls: 'state-thinking' };
    if (speechState === 'PAUSED') return { label: '⏸️ Paused', cls: 'state-paused' };
    if (status === 'preparing') return { label: 'Preparing your lesson...', cls: 'state-preparing' };
    if (status === 'active') return { label: '● Teaching', cls: 'state-speaking' };
    return { label: '● Ready to learn', cls: 'state-idle' };
  };

  const stateInfo = getTeacherStateInfo();
  const [dialogueExpanded, setDialogueExpanded] = useState(false);

  return (
    <section className="teacher-stage-card-42" aria-label="AI Teacher Stage">
      {/* Hidden audio element for genuine neural spoken narration */}
      <audio
        ref={audioRef}
        onEnded={() => {
          setSpeechState('IDLE');
          if (typeof setTeacherState === 'function') {
            setTeacherState(currentStep === 'question' ? 'listening' : 'idle');
          }
        }}
        onError={(e) => {
          console.warn('Audio element error:', e);
        }}
      />

      {/* 1. Large Hero Video or Centered Animated Teacher Spotlight */}
      <div className="stage-main-canvas-area flex flex-col items-center justify-center flex-1">
        {hasVideoUrl ? (
          <div className="teacher-video-container w-full rounded-2xl overflow-hidden border border-indigo-100">
            <video
              src={activeVideoUrl}
              controls
              autoPlay
              className="teacher-video-element w-full"
              title="AI Teacher Lesson Video"
            />
            {exportedVideoUrl && (
              <div style={{ padding: '8px 12px', textAlign: 'center', background: '#F7F8FC', borderTop: '1px solid #E6E6FA' }}>
                <span style={{ fontSize: '13px', color: '#4A3A73', fontWeight: 600 }}>
                  🎬 Playing Exported Video (.webm)
                </span>
                <button
                  type="button"
                  style={{ marginLeft: '12px', fontSize: '12px', color: '#64748B', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
                  onClick={() => setExportedVideoUrl(null)}
                >
                  Return to Live Stage
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="teacher-avatar-stage-spotlight w-full flex flex-col items-center" ref={canvasContainerRef}>
            {/* Centered Avatar Display Area (260-300px wide x 240-270px high) */}
            <div className="avatar-stage-center relative flex items-center justify-center my-1">
              <div className={`teacher-character-stage-wrapper ${avatarVisualState.toLowerCase()}`}>
                <div className="teacher-aura-ring" />
                <canvas
                  ref={canvasRef}
                  className="teacher-avatar-canvas"
                  role="img"
                  aria-label={`Professor Teachie AI Teacher - ${avatarVisualState} state`}
                  style={{
                    display: 'block',
                    width: '260px',
                    height: '240px',
                    borderRadius: '24px',
                    margin: '0 auto',
                  }}
                />
              </div>
            </div>

            {/* Professor Identity & Dynamic Status Pill */}
            <div className="teacher-identity-strip text-center mt-2">
              <h2 className="teacher-brand-name font-extrabold text-lg md:text-xl text-indigo-950 tracking-tight m-0">
                Professor Teachie
              </h2>
              <div className="mt-1">
                <span className={`teacher-state-badge ${stateInfo.cls} inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold`}>
                  {stateInfo.label}
                </span>
              </div>
            </div>

            {/* Teacher Speaking Area: Compact 3-4 lines with expand option */}
            <div className="teacher-speaking-box mt-3 px-4 py-3 rounded-2xl bg-white/90 border border-indigo-100/80 shadow-xs max-w-md w-full text-center">
              <p
                className={`teacher-speech-text text-sm font-medium text-slate-800 leading-relaxed italic m-0 ${
                  !dialogueExpanded ? 'line-clamp-3' : ''
                }`}
              >
                {getTeacherDialogue()}
              </p>
              {delivery?.content && delivery.content.length > 180 && (
                <button
                  type="button"
                  className="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 mt-1 bg-transparent border-none cursor-pointer"
                  onClick={() => setDialogueExpanded(!dialogueExpanded)}
                >
                  {dialogueExpanded ? '▲ Show less' : '▼ Read more'}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 2. Compact Audio & Video Controls Bar (Height 40-44px, radius 12-16px) */}
      <div className="teacher-audio-bar flex items-center justify-between gap-2 mt-4 pt-3 border-t border-indigo-100/70 w-full" aria-label="Audio Playback Controls">
        <div className="audio-controls-cluster flex items-center flex-wrap gap-2">
          {speechState !== 'SPEAKING' ? (
            <button
              type="button"
              className={`btn-audio-pill btn-audio-primary ${hasDelivery && speechState === 'IDLE' ? 'btn-audio-glow' : ''}`}
              onClick={handlePlay}
              disabled={!hasDelivery || !ttsSupported}
              aria-label={speechState === 'PAUSED' ? 'Resume Speech' : 'Play Voice'}
              title={speechState === 'PAUSED' ? 'Resume voice explanation' : 'Listen to teacher voice'}
            >
              <span className="btn-audio-icon">{speechState === 'PAUSED' ? '▶' : '🔊'}</span>
              <span className="btn-audio-text">{speechState === 'PAUSED' ? 'Resume' : 'Play'}</span>
            </button>
          ) : (
            <button
              type="button"
              className="btn-audio-pill btn-audio-warning"
              onClick={handlePause}
              aria-label="Pause Speech"
              title="Pause teacher voice"
            >
              <span className="btn-audio-icon">⏸</span>
              <span className="btn-audio-text">Pause</span>
            </button>
          )}

          <button
            type="button"
            className="btn-audio-pill btn-audio-secondary"
            onClick={handleReplay}
            disabled={!hasDelivery || !ttsSupported}
            aria-label="Replay Narration"
            title="Replay explanation from start"
          >
            <span className="btn-audio-icon">🔄</span>
            <span className="btn-audio-text">Replay</span>
          </button>

          <button
            type="button"
            className="btn-audio-pill btn-audio-secondary"
            onClick={handleStop}
            disabled={speechState === 'IDLE'}
            aria-label="Stop Speech"
            title="Stop voice"
          >
            <span className="btn-audio-icon">⏹</span>
            <span className="btn-audio-text">Stop</span>
          </button>

          {/* Speed Selector */}
          <div className="rate-selector-pill flex items-center gap-1 px-2 py-1 bg-white border border-slate-200 rounded-xl">
            <span className="rate-label text-xs text-slate-500 font-bold">Speed:</span>
            <select
              className="rate-select text-xs font-bold text-slate-800 bg-transparent border-none cursor-pointer outline-none"
              value={speechRate}
              onChange={handleRateChange}
              disabled={!ttsSupported}
              aria-label="Speech Speed"
            >
              <option value="0.85">0.85×</option>
              <option value="1.0">1.0×</option>
              <option value="1.15">1.15×</option>
              <option value="1.3">1.3×</option>
            </select>
          </div>

          {/* Auto-narrate Toggle */}
          <label className="auto-narrate-pill flex items-center gap-1.5 px-2.5 py-1.5 bg-white border border-slate-200 rounded-xl cursor-pointer text-xs font-bold text-slate-700 hover:bg-slate-50 transition-all" title="Automatically speak when new concepts arrive">
            <input
              type="checkbox"
              checked={autoNarrate}
              onChange={(e) => setAutoNarrate(e.target.checked)}
              className="accent-indigo-600 rounded"
            />
            <span>✓ Auto</span>
          </label>
        </div>

        {/* Video Export Artifact Button */}
        <div className="audio-controls-export">
          <button
            type="button"
            className="btn-audio-pill btn-audio-export flex items-center gap-1 text-xs"
            onClick={handleExportVideo}
            disabled={videoExporting || !hasDelivery}
            title="Export this lesson as an authentic WebM video artifact"
          >
            <span>{videoExporting ? `🎬 ${videoProgress}%` : '🎬 Video'}</span>
          </button>
        </div>
      </div>

      {/* 3. Non-blocking Voice & Video Notices */}
      {videoExportToast && (
        <div className="tts-notice-banner mt-2" style={{ background: '#EEF7FC', borderColor: '#AEC6CF', color: '#2B3A67' }} role="status">
          <span className="notice-icon">🎉</span>
          <span>{videoExportToast}</span>
          <button type="button" className="btn btn-xs btn-link" onClick={() => setVideoExportToast(null)}>
            Dismiss
          </button>
        </div>
      )}

      {speechError && (
        <div className="tts-notice-banner notice-error mt-2" role="alert">
          <span className="notice-icon">⚠️</span>
          <span>{speechError}</span>
          <button type="button" className="btn btn-xs btn-link" onClick={() => setSpeechError(null)}>
            Dismiss
          </button>
        </div>
      )}
    </section>
  );
}
