import * as THREE from 'three';

// Exponential moving average for a THREE.Vector3
export function lerpVector3(current, target, alpha) {
  current.lerp(target, alpha);
}

// Simple 1D EMA
export class EMAScalar {
  constructor(alpha = 0.2) {
    this.alpha = alpha;
    this.value = null;
  }

  update(next) {
    if (this.value === null) {
      this.value = next;
    } else {
      this.value += this.alpha * (next - this.value);
    }
    return this.value;
  }
}

// Smooths a {x, y} landmark position
export class LandmarkSmoother {
  constructor(alpha = 0.25) {
    this.x = new EMAScalar(alpha);
    this.y = new EMAScalar(alpha);
  }

  update(point) {
    return {
      x: this.x.update(point.x),
      y: this.y.update(point.y),
    };
  }
}
