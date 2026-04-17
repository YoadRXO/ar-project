# AR Hand Control — Windows App

Control your PC with hand gestures using your webcam. No mouse or keyboard needed.

## Installation

1. Download and unzip `ARHandControl.zip`
2. Open the `ARHandControl` folder
3. Double-click `ARHandControl.exe`

No Python, Node.js, or install required.

## Launch Options

On startup you'll see a menu with two modes:

| Mode | Description |
|---|---|
| **Play with Camera** | Opens a live window showing your hand skeleton and the active gesture |
| **Run as Background Service** | Runs silently in the background — gestures work system-wide with no overlay |

## Gestures

### Zoom In / Zoom Out — Open Palm

Hold your hand open with **all 4 fingers extended**.

- **Move hand closer to camera** → Zoom In
- **Move hand farther from camera** → Zoom Out

> The app detects the apparent size of your hand and maps it to browser zoom (Ctrl+Scroll).

---

### Scroll Up / Scroll Down — Two Fingers

Raise your **index and middle fingers** only (ring and pinky folded down).

- **Fingers held straight/flat** → Scroll Up
- **Fingers bent / curled downward** → Scroll Down

---

### Scroll Left / Scroll Right — Two Fingers Tilted

Same two-finger pose as above, but tilt the fingers sideways:

- **Tilt fingers to the left** → Scroll Right
- **Tilt fingers to the right** → Scroll Left

---

### Pause — Fist

Close your hand into a **fist**. All gesture control stops until you open your hand again.

## Tips

- Keep your hand visible and centered in the camera frame
- Good lighting improves tracking accuracy
- The app shows live FPS in the top-right corner of the camera window
