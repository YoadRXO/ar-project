import { useRef, useState, useCallback, useEffect } from 'react';
import * as THREE from 'three';
import { useHandTracking } from '../hooks/useHandTracking.js';
import { useThreeScene } from '../hooks/useThreeScene.js';
import { useScrollControl } from '../hooks/useScrollControl.js';
import { isPinching, getPinchCenter, countExtendedFingers, isFist, SKELETON } from '../utils/gestures.js';
import { LandmarkSmoother } from '../utils/smoothing.js';

const smoother = new LandmarkSmoother(0.6);
const targetPos = new THREE.Vector3();
const targetScale = new THREE.Vector3(1, 1, 1);
const camTarget = new THREE.Vector3(0, 0, 5);

const FINGER_LABELS = ['Index', 'Middle', 'Ring', 'Pinky'];
const FINGER_COLORS = ['#ffd93d', '#6bcb77', '#4d96ff', '#c77dff'];
const COUNT_COLORS = [0xff4444, 0xffd93d, 0x6bcb77, 0xc77dff, 0x4fc3f7];

const DIR_ARROWS = { right: '→', left: '←', up: '↑', down: '↓', forward: '⊕', backward: '⊖' };
const DIR_LABELS = { right: 'Scroll Right', left: 'Scroll Left', up: 'Scroll Up', down: 'Scroll Down', forward: 'Zoom In', backward: 'Zoom Out' };

function drawSkeleton(ctx, landmarks, w, h) {
  const toC = (lm) => ({ x: (1 - lm.x) * w, y: lm.y * h });
  for (const { color, pairs, tips } of SKELETON) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (const [a, b] of pairs) {
      const pa = toC(landmarks[a]);
      const pb = toC(landmarks[b]);
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
    }
    ctx.stroke();
    for (const tipIdx of tips) {
      const p = toC(landmarks[tipIdx]);
      ctx.beginPath();
      ctx.arc(p.x, p.y, 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  }
  for (let i = 0; i < 21; i++) {
    if ([4, 8, 12, 16, 20].includes(i)) continue;
    const p = toC(landmarks[i]);
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.75)';
    ctx.fill();
  }
}

export default function ARScene() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const handCanvasRef = useRef(null);
  const { cubeRef, cameraRef } = useThreeScene(canvasRef);
  const scrollControl = useScrollControl();

  const [status, setStatus] = useState('Show your hand');
  const [fingerStates, setFingerStates] = useState([false, false, false, false]);
  const [fist, setFist] = useState(false);
  const [scrollMode, setScrollMode] = useState(false);
  const [direction, setDirection] = useState(null);

  useEffect(() => {
    const resize = () => {
      const c = handCanvasRef.current;
      if (!c) return;
      c.width = window.innerWidth;
      c.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  // Clear direction arrow after a short delay
  const dirTimerRef = useRef(null);
  const showDirection = useCallback((dir) => {
    setDirection(dir);
    clearTimeout(dirTimerRef.current);
    if (dir) {
      dirTimerRef.current = setTimeout(() => setDirection(null), 400);
    }
  }, []);

  const handleResults = useCallback((results) => {
    const ctx = handCanvasRef.current?.getContext('2d');
    if (ctx) ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    const landmarks = results.multiHandLandmarks?.[0];

    if (!landmarks || !cubeRef.current || !cameraRef.current) {
      scrollControl.reset();
      setStatus('Show your hand');
      setFingerStates([false, false, false, false]);
      setFist(false);
      setScrollMode(false);
      showDirection(null);
      return;
    }

    if (ctx) drawSkeleton(ctx, landmarks, ctx.canvas.width, ctx.canvas.height);

    const extCount = countExtendedFingers(landmarks);
    const fistNow = isFist(landmarks);
    // Open palm (3+ fingers) = scroll mode; fist or pinch = cube mode
    const inScrollMode = extCount >= 3;

    const states = [
      landmarks[8].y < landmarks[5].y,
      landmarks[12].y < landmarks[9].y,
      landmarks[16].y < landmarks[13].y,
      landmarks[20].y < landmarks[17].y,
    ];
    setFingerStates(states);
    setFist(fistNow);
    setScrollMode(inScrollMode);

    if (inScrollMode) {
      // --- SCROLL / CAMERA MODE ---
      const { dx, dy, dz, direction: dir } = scrollControl.compute(landmarks);

      // Camera panning: negate dx (video is mirrored), negate dy (MediaPipe y is inverted)
      camTarget.x -= dx * 10;
      camTarget.y -= dy * 8;
      // Z: hand bigger → zoom in → camera closer (lower z)
      camTarget.z -= dz * 40;
      camTarget.z = THREE.MathUtils.clamp(camTarget.z, 1.5, 12);

      cameraRef.current.position.lerp(camTarget, 0.12);

      // Also scroll the browser window (useful when page has content)
      if (Math.abs(dx) > 0.006 || Math.abs(dy) > 0.006) {
        window.scrollBy(-dx * 800, dy * 600);
      }

      if (dir) showDirection(dir);
      setStatus(`Scroll mode — ${DIR_LABELS[dir] ?? 'move hand to scroll'}`);
    } else {
      // --- CUBE INTERACTION MODE ---
      scrollControl.reset();

      // Ease camera back to default when leaving scroll mode
      camTarget.set(0, 0, 5);
      cameraRef.current.position.lerp(camTarget, 0.05);

      const pinch = isPinching(landmarks);
      const center = getPinchCenter(landmarks);
      const smoothed = smoother.update(center);

      const x = (smoothed.x - 0.5) * -8;
      const y = -(smoothed.y - 0.5) * 6;

      targetPos.set(x, y, 0);
      cubeRef.current.position.lerp(targetPos, 0.5);

      const scaleVal = fistNow ? 1.8 : 0.8 + extCount * 0.15;
      targetScale.setScalar(scaleVal);
      cubeRef.current.scale.lerp(targetScale, 0.35);

      cubeRef.current.material.color.set(COUNT_COLORS[extCount] ?? COUNT_COLORS[4]);
      cubeRef.current.material.emissive.set(
        fistNow ? 0x660000 : pinch ? 0x331a00 : 0x000000
      );
      cubeRef.current.userData.held = pinch || fistNow;

      setStatus(fistNow ? 'Fist!' : pinch ? 'Pinching!' : 'Cube mode');
    }
  }, [cubeRef, cameraRef, scrollControl, showDirection]);

  useHandTracking(videoRef, handleResults);

  return (
    <div style={styles.root}>
      <video ref={videoRef} autoPlay playsInline muted style={styles.video} />
      <canvas ref={handCanvasRef} style={styles.overlay} />
      <canvas ref={canvasRef} style={styles.overlay} />

      {/* Direction arrow — shown during scroll gestures */}
      {direction && (
        <div style={styles.dirArrow}>
          <span style={styles.dirGlyph}>{DIR_ARROWS[direction]}</span>
          <span style={styles.dirLabel}>{DIR_LABELS[direction]}</span>
        </div>
      )}

      {/* Mode pill */}
      <div style={styles.modePill}>
        <span style={{
          ...styles.modeBadge,
          background: scrollMode ? 'rgba(0,200,100,0.85)' : 'rgba(30,60,160,0.85)',
        }}>
          {scrollMode ? '✋ Scroll Mode' : '✊ Cube Mode'}
        </span>
      </div>

      {/* Finger state indicators */}
      <div style={styles.fingerHud}>
        {FINGER_LABELS.map((label, i) => (
          <div key={label} style={{
            ...styles.fingerBadge,
            background: fingerStates[i] ? FINGER_COLORS[i] : 'rgba(0,0,0,0.45)',
            color: fingerStates[i] ? '#000' : '#888',
          }}>
            {label}
          </div>
        ))}
      </div>

      <div style={styles.hud}>
        <span style={{
          ...styles.badge,
          background: fist ? '#ff4444' : scrollMode ? '#00c864' : '#1a237e',
          boxShadow: fist ? '0 0 20px rgba(255,68,68,0.7)' : 'none',
        }}>
          {status}
        </span>
      </div>

      <div style={styles.hint}>
        ✊ Fist / Pinch = cube mode &nbsp;·&nbsp; ✋ Open palm (3+ fingers) = scroll mode
      </div>
    </div>
  );
}

const styles = {
  root: { position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden', background: '#000' },
  video: { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' },
  overlay: { position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' },
  dirArrow: {
    position: 'absolute', top: '50%', left: '50%',
    transform: 'translate(-50%, -50%)',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    background: 'rgba(0,0,0,0.55)', borderRadius: 20, padding: '16px 30px',
    pointerEvents: 'none', animation: 'none',
  },
  dirGlyph: { fontSize: 64, lineHeight: 1, color: '#fff' },
  dirLabel: { fontSize: 14, color: 'rgba(255,255,255,0.75)', fontFamily: 'system-ui, sans-serif', marginTop: 6 },
  modePill: { position: 'absolute', top: 20, right: 20, zIndex: 10 },
  modeBadge: {
    display: 'inline-block', padding: '7px 16px', borderRadius: 20,
    color: '#fff', fontSize: 13, fontFamily: 'system-ui, sans-serif', fontWeight: 700,
    transition: 'background 0.2s',
  },
  fingerHud: { position: 'absolute', bottom: 55, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 8 },
  fingerBadge: { padding: '5px 12px', borderRadius: 12, fontSize: 12, fontFamily: 'system-ui, sans-serif', fontWeight: 700, transition: 'background 0.15s, color 0.15s' },
  hud: { position: 'absolute', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 10 },
  badge: { display: 'inline-block', padding: '8px 20px', borderRadius: 24, color: '#fff', fontSize: 15, fontFamily: 'system-ui, sans-serif', fontWeight: 600, letterSpacing: 0.5, transition: 'background 0.15s, box-shadow 0.15s' },
  hint: { position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', color: 'rgba(255,255,255,0.55)', fontSize: 12, fontFamily: 'system-ui, sans-serif', whiteSpace: 'nowrap' },
};
