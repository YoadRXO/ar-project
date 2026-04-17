# AR Hand Tracking — MVP

## Quick Start

### Frontend
```bash
cd ar-hand-app
npm install
npm run dev
# Open http://localhost:5173
```

### Backend (optional for MVP)
```bash
cd ar-backend
npm install
npm run start:dev
# Runs on http://localhost:3001
```

## How It Works

```
Camera → MediaPipe Hands → Gesture Detection → Three.js Object → Visual Feedback
```

- **Pinch** (thumb + index finger close together) = grab the cube
- **Release** = drop the cube, it resumes idle rotation
- A dot tracks your fingertip in screen space
- EMA smoothing prevents jitter

## Save a Session (Backend)
```http
POST http://localhost:3001/sessions
Content-Type: application/json

{
  "position": { "x": 0.2, "y": 0.1, "z": 0 },
  "timestamp": 1713000000000
}
```

## File Structure
```
ar-project/
├── ar-hand-app/          # React + Vite frontend
│   └── src/
│       ├── components/
│       │   └── ARScene.jsx        # Main AR component
│       ├── hooks/
│       │   ├── useHandTracking.js # MediaPipe integration
│       │   └── useThreeScene.js   # Three.js scene setup
│       └── utils/
│           ├── gestures.js        # Pinch detection
│           └── smoothing.js       # EMA smoother
└── ar-backend/           # NestJS backend
    └── src/
        ├── sessions/              # POST /sessions endpoint
        └── main.ts
```

## Windows Desktop App (EXE)

Builds a native Windows executable using PyInstaller.

### Build

```bash
# From WSL terminal, inside ar-windows-input/
cmd.exe /c "$(wslpath -w "$(pwd)/build.bat")"
```

Output: `ar-windows-input/dist/ARHandControl/ARHandControl.exe`

### Run

Double-click `ARHandControl.exe` inside `dist/ARHandControl/`. Keep the entire folder together — the exe depends on files alongside it.

### Share

Zip the whole `dist/ARHandControl/` folder and send it. No install required on the recipient's machine.