# AR Hand Tracking

## Installation

### Requirements

- Node.js 18+
- A webcam

### Setup

```bash
# Frontend
cd ar-hand-app
npm install
npm run dev
# Open http://localhost:5173
```

```bash
# Backend (optional)
cd ar-backend
npm install
npm run start:dev
# Runs on http://localhost:3001
```

## Usage

Open `http://localhost:5173` in your browser and allow camera access.

### Gestures

| Gesture | Action |
|---|---|
| Pinch (thumb + index close) | Grab the cube |
| Release pinch | Drop the cube |
| Scroll down claw (fingers curl) | Scroll down |

A dot tracks your fingertip in real time. EMA smoothing reduces jitter.

## Windows Desktop App

A standalone Windows EXE is available — no browser or Node.js required.

See [`ar-windows-input/README.md`](ar-windows-input/README.md) for build and distribution instructions.