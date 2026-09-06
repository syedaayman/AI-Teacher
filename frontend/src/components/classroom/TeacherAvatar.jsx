import React, { useEffect, useRef } from 'react';

/**
 * TeacherAvatar Component
 * Authentic animated AI Teacher rendered on dynamic HTML5 Canvas.
 * Features:
 * - Dynamic ResizeObserver syncing canvas.width/height with DOM client dimensions and devicePixelRatio
 * - Relative percentage coordinates centered at (width * 0.5, height * 0.5)
 * - Full head-to-chest portrait fitting safely inside viewbox with generous framing padding
 * - Animated expressive states: IDLE, SPEAKING, THINKING, LISTENING, ENCOURAGING, PAUSED
 */
export default function TeacherAvatar({
  state = 'IDLE',
  teacherName = 'Professor Teachie',
  size = 'large',
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);

  const normState = (state || 'IDLE').toUpperCase();
  const stateLabel = normState === 'SPEAKING' ? 'Speaking' : 
                     normState === 'THINKING' ? 'Thinking' : 
                     normState === 'LISTENING' ? 'Listening' : 
                     normState === 'ENCOURAGING' ? 'Encouraging' : 
                     normState === 'PAUSED' ? 'Paused' : 'Ready';

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const updateDimensions = () => {
      const dpr = window.devicePixelRatio || 1;
      const clientWidth = container.clientWidth || 320;
      const clientHeight = container.clientHeight || 320;

      canvas.width = Math.floor(clientWidth * dpr);
      canvas.height = Math.floor(clientHeight * dpr);
      canvas.style.width = `${clientWidth}px`;
      canvas.style.height = `${clientHeight}px`;
    };

    updateDimensions();

    const resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });
    resizeObserver.observe(container);

    let animationFrameId;

    const render = (time) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const width = canvas.width / dpr;
      const height = canvas.height / dpr;

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.scale(dpr, dpr);

      drawCanvasAvatar(ctx, width, height, normState, time);

      ctx.restore();
      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      resizeObserver.disconnect();
      cancelAnimationFrame(animationFrameId);
    };
  }, [normState]);

  return (
    <div
      ref={containerRef}
      className={`teacher-avatar-canvas-container size-${size} state-${normState.toLowerCase()}`}
      role="img"
      aria-label={`${teacherName} - ${normState} state`}
      style={{
        width: '100%',
        height: '100%',
        minHeight: '220px',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div className={`teacher-character-stage-wrapper ${normState.toLowerCase()}`}>
        <div className="teacher-aura-ring" />
        <img
          src="/images/teacher_hero.jpg"
          alt={teacherName}
          className="teacher-character-portrait"
          onError={(e) => {
            e.target.style.display = 'none';
            if (canvasRef.current) canvasRef.current.style.display = 'block';
          }}
        />
        <div className={`stage-state-bubble bubble-${normState.toLowerCase()}`}>
          {stateLabel}
        </div>
      </div>

      <canvas
        ref={canvasRef}
        className="teacher-avatar-canvas"
        style={{
          display: 'none',
          width: '100%',
          height: '100%',
          maxWidth: '100%',
          maxHeight: '100%',
        }}
      />
    </div>
  );
}

/**
 * Procedural Canvas Avatar Drawer
 * Coordinates (head, eyes, mouth, headset, torso) are all computed as relative percentages
 * centered at (width * 0.5, height * 0.5).
 */
export function drawCanvasAvatar(ctx, width, height, visualState, timestamp) {
  const cx = width * 0.5;
  const cy = height * 0.5;

  // Scale factor: keep head to chest within ~72% of viewbox for guaranteed framing padding
  const scale = Math.min(width, height) * 0.72;

  const isSpeaking = visualState === 'SPEAKING';
  const isThinking = visualState === 'THINKING';
  const isListening = visualState === 'LISTENING';
  const isEncouraging = visualState === 'ENCOURAGING';

  // 1. Studio Holographic Aura Glow Backdrop (centered at cx, cy)
  const auraGrad = ctx.createRadialGradient(cx, cy, scale * 0.1, cx, cy, scale * 0.58);
  const auraColor = isEncouraging
    ? 'rgba(16, 185, 129, '
    : isListening
    ? 'rgba(6, 182, 212, '
    : isThinking
    ? 'rgba(129, 140, 248, '
    : isSpeaking
    ? 'rgba(56, 189, 248, '
    : 'rgba(139, 92, 246, ';
  auraGrad.addColorStop(0, auraColor + '0.22)');
  auraGrad.addColorStop(0.7, auraColor + '0.06)');
  auraGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');
  ctx.fillStyle = auraGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, scale * 0.58, 0, Math.PI * 2);
  ctx.fill();

  // Outer orbital accent ring
  ctx.strokeStyle = auraColor + (isSpeaking || isListening ? '0.55)' : '0.28)');
  ctx.lineWidth = Math.max(1.5, scale * 0.008);
  if (isThinking) {
    ctx.setLineDash([scale * 0.04, scale * 0.03]);
    ctx.lineDashOffset = -(timestamp / 40);
  } else {
    ctx.setLineDash([]);
  }
  ctx.beginPath();
  ctx.arc(cx, cy, scale * 0.52, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);

  // 2. Torso / Blazer (Chest-to-shoulders framing safely within viewbox)
  const torsoTopY = cy + scale * 0.16;
  const torsoBottomY = cy + scale * 0.44;
  const shoulderHalfWidth = scale * 0.38;

  const blazerGrad = ctx.createLinearGradient(cx, torsoTopY, cx, torsoBottomY);
  if (isEncouraging) {
    blazerGrad.addColorStop(0, '#047857');
    blazerGrad.addColorStop(1, '#064e3b');
  } else {
    blazerGrad.addColorStop(0, '#1E293B');
    blazerGrad.addColorStop(1, '#0F172A');
  }
  ctx.fillStyle = blazerGrad;
  ctx.beginPath();
  ctx.moveTo(cx - shoulderHalfWidth, torsoBottomY);
  ctx.bezierCurveTo(
    cx - shoulderHalfWidth * 0.9, torsoTopY + scale * 0.06,
    cx - scale * 0.14, torsoTopY,
    cx, torsoTopY
  );
  ctx.bezierCurveTo(
    cx + scale * 0.14, torsoTopY,
    cx + shoulderHalfWidth * 0.9, torsoTopY + scale * 0.06,
    cx + shoulderHalfWidth, torsoBottomY
  );
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = auraColor + '0.4)';
  ctx.lineWidth = Math.max(1, scale * 0.006);
  ctx.stroke();

  // Inner Shirt & Collar
  ctx.fillStyle = '#FFFFFF';
  ctx.beginPath();
  ctx.moveTo(cx - scale * 0.08, torsoTopY);
  ctx.lineTo(cx, torsoTopY + scale * 0.14);
  ctx.lineTo(cx + scale * 0.08, torsoTopY);
  ctx.closePath();
  ctx.fill();

  // Collar Ribbon / Tie
  ctx.fillStyle = isEncouraging ? '#10B981' : '#6366F1';
  ctx.beginPath();
  ctx.moveTo(cx - scale * 0.02, torsoTopY + scale * 0.09);
  ctx.lineTo(cx + scale * 0.02, torsoTopY + scale * 0.09);
  ctx.lineTo(cx + scale * 0.03, torsoBottomY);
  ctx.lineTo(cx - scale * 0.03, torsoBottomY);
  ctx.closePath();
  ctx.fill();

  // 3. Neck
  const headY = cy - scale * 0.10;
  const headRx = scale * 0.19;
  const headRy = scale * 0.23;
  const neckWidth = scale * 0.12;
  const neckTop = headY + headRy * 0.65;
  const neckBottom = torsoTopY + scale * 0.03;

  ctx.fillStyle = '#E6B89C';
  ctx.fillRect(cx - neckWidth * 0.5, neckTop, neckWidth, neckBottom - neckTop);

  // 4. Head / Face (Centered at cx, headY with generous head padding from viewbox top)
  const faceGrad = ctx.createLinearGradient(cx, headY - headRy, cx, headY + headRy);
  faceGrad.addColorStop(0, '#FCE7D6');
  faceGrad.addColorStop(1, '#E6B89C');
  ctx.fillStyle = faceGrad;
  ctx.beginPath();
  ctx.ellipse(cx, headY, headRx, headRy, 0, 0, Math.PI * 2);
  ctx.fill();

  // 5. Hair Silhouette
  const hairGrad = ctx.createLinearGradient(cx - headRx, headY - headRy, cx + headRx, headY);
  hairGrad.addColorStop(0, '#1E293B');
  hairGrad.addColorStop(1, '#0F172A');
  ctx.fillStyle = hairGrad;
  ctx.beginPath();
  ctx.arc(cx, headY - scale * 0.02, headRx * 1.08, Math.PI * 0.82, Math.PI * 2.18);
  ctx.bezierCurveTo(
    cx + headRx * 0.95, headY - headRy * 0.4,
    cx + headRx * 0.5, headY - headRy * 0.85,
    cx, headY - headRy * 0.8
  );
  ctx.bezierCurveTo(
    cx - headRx * 0.4, headY - headRy * 0.85,
    cx - headRx * 0.95, headY - headRy * 0.4,
    cx - headRx * 1.05, headY - scale * 0.02
  );
  ctx.closePath();
  ctx.fill();

  // 6. Eyebrows
  const leftBrowX = cx - scale * 0.075;
  const rightBrowX = cx + scale * 0.075;
  const browBaseY = headY - scale * 0.07;
  const leftBrowY = isThinking ? browBaseY - scale * 0.02 : browBaseY;
  const rightBrowY = isThinking ? browBaseY + scale * 0.01 : browBaseY;

  ctx.strokeStyle = '#1E293B';
  ctx.lineWidth = Math.max(2, scale * 0.015);
  ctx.lineCap = 'round';

  ctx.beginPath();
  ctx.moveTo(leftBrowX - scale * 0.04, leftBrowY);
  ctx.quadraticCurveTo(leftBrowX, leftBrowY - scale * 0.015, leftBrowX + scale * 0.035, leftBrowY);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(rightBrowX - scale * 0.035, rightBrowY);
  ctx.quadraticCurveTo(rightBrowX, rightBrowY - scale * 0.015, rightBrowX + scale * 0.04, rightBrowY);
  ctx.stroke();

  // 7. Eyes with Natural Blinking
  const leftEyeX = cx - scale * 0.075;
  const rightEyeX = cx + scale * 0.075;
  const eyeY = headY - scale * 0.02;
  const eyeRadius = scale * 0.032;
  const isBlink = Math.sin(timestamp / 380) > 0.94;

  if (isBlink) {
    ctx.strokeStyle = '#1E293B';
    ctx.lineWidth = Math.max(2, scale * 0.014);
    ctx.beginPath();
    ctx.moveTo(leftEyeX - eyeRadius, eyeY);
    ctx.quadraticCurveTo(leftEyeX, eyeY + scale * 0.008, leftEyeX + eyeRadius, eyeY);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(rightEyeX - eyeRadius, eyeY);
    ctx.quadraticCurveTo(rightEyeX, eyeY + scale * 0.008, rightEyeX + eyeRadius, eyeY);
    ctx.stroke();
  } else {
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.ellipse(leftEyeX, eyeY, eyeRadius * 1.1, eyeRadius, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(rightEyeX, eyeY, eyeRadius * 1.1, eyeRadius, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#0F172A';
    ctx.beginPath();
    ctx.arc(leftEyeX, eyeY, eyeRadius * 0.7, 0, Math.PI * 2);
    ctx.arc(rightEyeX, eyeY, eyeRadius * 0.7, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(leftEyeX + scale * 0.008, eyeY - scale * 0.008, eyeRadius * 0.28, 0, Math.PI * 2);
    ctx.arc(rightEyeX + scale * 0.008, eyeY - scale * 0.008, eyeRadius * 0.28, 0, Math.PI * 2);
    ctx.fill();
  }

  // Glasses Frame
  ctx.strokeStyle = isEncouraging ? '#10B981' : '#38BDF8';
  ctx.lineWidth = Math.max(1.5, scale * 0.01);
  const glassWidth = scale * 0.085;
  const glassHeight = scale * 0.065;
  ctx.strokeRect(leftEyeX - glassWidth * 0.5, eyeY - glassHeight * 0.5, glassWidth, glassHeight);
  ctx.strokeRect(rightEyeX - glassWidth * 0.5, eyeY - glassHeight * 0.5, glassWidth, glassHeight);
  ctx.beginPath();
  ctx.moveTo(leftEyeX + glassWidth * 0.5, eyeY);
  ctx.lineTo(rightEyeX - glassWidth * 0.5, eyeY);
  ctx.stroke();

  // 8. Nose
  ctx.strokeStyle = '#D4A373';
  ctx.lineWidth = Math.max(1.5, scale * 0.01);
  ctx.beginPath();
  ctx.moveTo(cx, headY);
  ctx.lineTo(cx - scale * 0.012, headY + scale * 0.045);
  ctx.lineTo(cx + scale * 0.012, headY + scale * 0.045);
  ctx.stroke();

  // 9. Mouth (Expressive & Speaking Cadence)
  const mouthY = headY + scale * 0.105;
  const mouthWidth = scale * 0.065;

  if (isSpeaking) {
    const mouthHeight = scale * 0.02 + Math.abs(Math.sin(timestamp / 110)) * (scale * 0.035);
    ctx.fillStyle = '#BE123C';
    ctx.beginPath();
    ctx.ellipse(cx, mouthY, mouthWidth, mouthHeight, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.ellipse(cx, mouthY - mouthHeight * 0.4, mouthWidth * 0.75, mouthHeight * 0.35, 0, 0, Math.PI);
    ctx.fill();

    ctx.strokeStyle = '#881337';
    ctx.lineWidth = Math.max(1, scale * 0.008);
    ctx.stroke();
  } else if (isEncouraging) {
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.moveTo(cx - mouthWidth * 1.1, mouthY - scale * 0.01);
    ctx.quadraticCurveTo(cx, mouthY + scale * 0.045, cx + mouthWidth * 1.1, mouthY - scale * 0.01);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = '#047857';
    ctx.lineWidth = Math.max(1.8, scale * 0.012);
    ctx.stroke();
  } else if (isListening) {
    ctx.strokeStyle = '#9F1239';
    ctx.lineWidth = Math.max(1.5, scale * 0.01);
    ctx.beginPath();
    ctx.moveTo(cx - mouthWidth * 0.7, mouthY);
    ctx.quadraticCurveTo(cx, mouthY + scale * 0.015, cx + mouthWidth * 0.7, mouthY);
    ctx.stroke();
  } else if (isThinking) {
    ctx.strokeStyle = '#9F1239';
    ctx.lineWidth = Math.max(1.5, scale * 0.01);
    ctx.beginPath();
    ctx.moveTo(cx - mouthWidth * 0.6, mouthY);
    ctx.quadraticCurveTo(cx, mouthY - scale * 0.01, cx + mouthWidth * 0.6, mouthY);
    ctx.stroke();
  } else {
    ctx.strokeStyle = '#9F1239';
    ctx.lineWidth = Math.max(1.8, scale * 0.012);
    ctx.beginPath();
    ctx.moveTo(cx - mouthWidth * 0.8, mouthY - scale * 0.005);
    ctx.quadraticCurveTo(cx, mouthY + scale * 0.022, cx + mouthWidth * 0.8, mouthY - scale * 0.005);
    ctx.stroke();
  }

  // 10. Headset & Microphone
  const earpieceX = cx + headRx * 0.95;
  const earpieceY = headY;
  const micTipX = cx + scale * 0.06;
  const micTipY = mouthY + scale * 0.015;

  ctx.strokeStyle = '#334155';
  ctx.lineWidth = Math.max(2, scale * 0.014);
  ctx.beginPath();
  ctx.arc(cx, headY - scale * 0.02, headRx * 1.08, Math.PI * 1.45, Math.PI * 1.95);
  ctx.stroke();

  ctx.fillStyle = isListening ? '#06B6D4' : '#3B82F6';
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(earpieceX - scale * 0.02, earpieceY - scale * 0.04, scale * 0.04, scale * 0.08, scale * 0.015);
  } else {
    ctx.rect(earpieceX - scale * 0.02, earpieceY - scale * 0.04, scale * 0.04, scale * 0.08);
  }
  ctx.fill();

  ctx.strokeStyle = '#64748B';
  ctx.lineWidth = Math.max(1.5, scale * 0.01);
  ctx.beginPath();
  ctx.moveTo(earpieceX, earpieceY + scale * 0.02);
  ctx.quadraticCurveTo(earpieceX - scale * 0.02, micTipY, micTipX, micTipY);
  ctx.stroke();

  const micColor = isSpeaking ? '#38BDF8' : isListening ? '#06B6D4' : '#94A3B8';
  ctx.fillStyle = micColor;
  ctx.beginPath();
  ctx.arc(micTipX, micTipY, scale * 0.018, 0, Math.PI * 2);
  ctx.fill();

  if (isListening) {
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.7)';
    ctx.lineWidth = Math.max(1, scale * 0.008);
    const pulseOffset = (timestamp / 250) % 1;
    ctx.beginPath();
    ctx.arc(micTipX, micTipY, scale * 0.025 + pulseOffset * scale * 0.03, -Math.PI * 0.4, Math.PI * 0.4);
    ctx.stroke();
  }
}
