export function isPinching(landmarks) {
  const thumb = landmarks[4];
  const index = landmarks[8];
  const dx = thumb.x - index.x;
  const dy = thumb.y - index.y;
  return Math.sqrt(dx * dx + dy * dy) < 0.05;
}

export function getPinchCenter(landmarks) {
  const thumb = landmarks[4];
  const index = landmarks[8];
  return {
    x: (thumb.x + index.x) / 2,
    y: (thumb.y + index.y) / 2,
  };
}

// Tips and their corresponding MCP (knuckle) indices
const FINGERS = [
  { tip: 8,  mcp: 5  }, // index
  { tip: 12, mcp: 9  }, // middle
  { tip: 16, mcp: 13 }, // ring
  { tip: 20, mcp: 17 }, // pinky
];

// Returns [index, middle, ring, pinky] booleans — true = extended
export function getFingerStates(landmarks) {
  return FINGERS.map(({ tip, mcp }) => landmarks[tip].y < landmarks[mcp].y);
}

// 0 = fist, 4 = all four fingers fully open
export function countExtendedFingers(landmarks) {
  return getFingerStates(landmarks).filter(Boolean).length;
}

export function isFist(landmarks) {
  return countExtendedFingers(landmarks) === 0;
}

// Hand skeleton connections grouped by finger for per-finger coloring
export const SKELETON = [
  { color: '#ff6b6b', pairs: [[0,1],[1,2],[2,3],[3,4]],            tips: [4]  },  // thumb
  { color: '#ffd93d', pairs: [[0,5],[5,6],[6,7],[7,8]],            tips: [8]  },  // index
  { color: '#6bcb77', pairs: [[0,9],[9,10],[10,11],[11,12]],       tips: [12] },  // middle
  { color: '#4d96ff', pairs: [[0,13],[13,14],[14,15],[15,16]],     tips: [16] },  // ring
  { color: '#c77dff', pairs: [[0,17],[17,18],[18,19],[19,20]],     tips: [20] },  // pinky
  { color: 'rgba(255,255,255,0.35)', pairs: [[5,9],[9,13],[13,17]], tips: []  },  // palm
];
