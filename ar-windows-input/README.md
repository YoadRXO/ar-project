# AR Hand Control — Windows EXE Builder

Builds a standalone Windows executable using PyInstaller. No Python or browser required on the target machine.

## Build

Run from a WSL terminal inside `ar-windows-input/`:

```bash
cmd.exe /c "$(wslpath -w "$(pwd)/build.bat")"
```

Output: `dist/ARHandControl/ARHandControl.exe`

## Run

Double-click `ARHandControl.exe` inside `dist/ARHandControl/`. Keep the entire folder together — the exe depends on files alongside it.

## Share / Distribute

Zip the whole `dist/ARHandControl/` folder and send it. No install required on the recipient's machine.

## Development

### Requirements

- Python 3.10+
- Install dependencies:

```bash
pip install -r requirements.txt
```

### Run without building

```bash
python main.py
```

### Files

| File | Purpose |
|---|---|
| `main.py` | Entry point |
| `gesture.py` | Gesture detection logic |
| `smoother.py` | EMA smoothing |
| `win_input.py` | Windows input simulation |
| `hand_landmarker.task` | MediaPipe model |
| `build.bat` | PyInstaller build script |
