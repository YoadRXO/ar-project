import { useRef } from 'react';

const THRESHOLD = 0.006; // min velocity to register a direction

export function useScrollControl() {
  const prevPos = useRef(null);
  const prevSize = useRef(null);

  function compute(landmarks) {
    const wrist = landmarks[0];
    const midMCP = landmarks[9];

    // Current palm center (average wrist + midMCP)
    const pos = {
      x: (wrist.x + midMCP.x) / 2,
      y: (wrist.y + midMCP.y) / 2,
    };

    // Apparent hand size as Z-depth proxy (larger = closer to camera)
    const size = Math.hypot(wrist.x - midMCP.x, wrist.y - midMCP.y);

    const result = { dx: 0, dy: 0, dz: 0, direction: null };

    if (prevPos.current !== null) {
      result.dx = pos.x - prevPos.current.x;
      result.dy = pos.y - prevPos.current.y;
      result.dz = size - (prevSize.current ?? size);

      const adx = Math.abs(result.dx);
      const ady = Math.abs(result.dy);
      const adz = Math.abs(result.dz);

      // Dominant axis determines displayed direction
      if (adz > 0.003 && adz > adx && adz > ady) {
        result.direction = result.dz > 0 ? 'forward' : 'backward';
      } else if (adx > THRESHOLD || ady > THRESHOLD) {
        if (adx > ady) {
          // dx is in raw MediaPipe space; video is mirrored so negate for display
          result.direction = result.dx < 0 ? 'right' : 'left';
        } else {
          result.direction = result.dy > 0 ? 'down' : 'up';
        }
      }
    }

    prevPos.current = pos;
    prevSize.current = size;
    return result;
  }

  function reset() {
    prevPos.current = null;
    prevSize.current = null;
  }

  return { compute, reset };
}
