"""
AR Hand → Windows Input Controller
====================================
Open palm  (3+ fingers) = scroll mode
  · Move hand left/right  → horizontal scroll
  · Move hand up/down     → vertical scroll
  · Move hand toward/away → browser zoom (Ctrl+scroll)

Fist / closed hand = paused (no scroll)

Controls:
  Q or ESC = quit
  P        = pause / resume
"""

import os
import sys
import time
import shutil
import tempfile
import threading
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from win_input import scroll_vertical, scroll_horizontal, zoom, move_mouse, right_click, get_screen_size
from smoother import PositionSmoother, EMA  # EMA still used for size_smoother
from gesture import (
    get_extended_fingers, is_scroll_mode, is_zoom_mode, is_fist, is_mouse_mode,
    get_palm_center, get_two_finger_center, get_hand_size,
    get_two_finger_curl, get_horizontal_tilt,
    FINGER_CONNECTIONS, FINGER_COLORS_BGR, FINGER_NAMES,
)

# ── tunables ──────────────────────────────────────────────────────────────────
DEAD_ZONE          = 0.005
SCROLL_H_SPEED     = 60
ZOOM_SPEED         = 12
POS_SMOOTH         = 0.5
ZOOM_THRESHOLD     = 0.012
ZOOM_BASELINE_RATE = 0.03

# Pose-based vertical scroll (up/down)
STRAIGHT_THRESHOLD = 0.12   # curl score above this → fingers flat  → scroll UP
CURL_THRESHOLD     = 0.06   # curl score below this → fingers bent   → scroll DOWN

# Pose-based horizontal scroll (left/right)
TILT_THRESHOLD     = 0.07   # tilt magnitude above this → scroll LEFT or RIGHT

SCROLL_POSE_SPEED  = 6      # scroll notches per second while holding any pose

# Clear-field guard — prevents face-touch (nose/ear scratch) from firing gestures
CLEAR_ZONE_Y_MIN   = 0.25   # palm center y must be BELOW top 25% of frame (face zone)
CLEAR_FIELD_FRAMES = 8      # consecutive frames in clear zone before gestures arm

# Mouse / pointer mode (index finger only)
MOUSE_SMOOTH       = 0.35   # EMA alpha for cursor — higher = more responsive
# ─────────────────────────────────────────────────────────────────────────────

MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)


def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print("Downloading hand tracking model (~9 MB) ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Download complete.\n")


def _get_fast_model_path() -> str:
    """
    python.exe is a Windows process — reading the model from the WSL
    filesystem (\\wsl.localhost\\...) is slow virtual I/O.
    Copy it to the Windows TEMP folder once so it loads from native NTFS.
    """
    tmp = os.path.join(tempfile.gettempdir(), "ar_hand_landmarker.task")
    if not os.path.exists(tmp):
        shutil.copy2(MODEL_PATH, tmp)
    return tmp


def _make_landmarker_options():
    return vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=_get_fast_model_path()),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )


# Pre-load everything in background the moment the script starts.
# Both the landmarker AND the camera are ready before the user clicks.
_preload_done       = threading.Event()
_preload_error      = [None]
_preloaded_landmarker = [None]
_preloaded_cap        = [None]

def _preload_model():
    try:
        ensure_model()
        # Keep landmarker alive — reused directly in main(), no second init
        _preloaded_landmarker[0] = vision.HandLandmarker.create_from_options(
            _make_landmarker_options()
        )
        # Open camera early so the first frame is instant
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_FPS, 60)
        _preloaded_cap[0] = cap
    except Exception as e:
        _preload_error[0] = e
    finally:
        _preload_done.set()

threading.Thread(target=_preload_model, daemon=True).start()


def draw_skeleton(frame, lm, h, w):
    tips = {4, 8, 12, 16, 20}
    for connections, color in zip(FINGER_CONNECTIONS, FINGER_COLORS_BGR):
        for a, b in connections:
            ax, ay = int(lm[a].x * w), int(lm[a].y * h)
            bx, by = int(lm[b].x * w), int(lm[b].y * h)
            cv2.line(frame, (ax, ay), (bx, by), color, 2, cv2.LINE_AA)

    for i in range(21):
        px, py = int(lm[i].x * w), int(lm[i].y * h)
        if i in tips:
            finger_idx = [4, 8, 12, 16, 20].index(i)
            col = FINGER_COLORS_BGR[finger_idx]
            cv2.circle(frame, (px, py), 8, col, -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 8, (255, 255, 255), 1, cv2.LINE_AA)
        else:
            cv2.circle(frame, (px, py), 4, (220, 220, 220), -1, cv2.LINE_AA)


def draw_hud(frame, h, w, zoom_active, scroll_active, mouse_active, paused, direction, finger_states, fps, armed=True):
    if paused:
        label, color = "PAUSED", (60, 60, 60)
    elif not armed:
        label, color = "hand near face...", (40, 40, 120)
    elif mouse_active:
        label, color = "MOUSE  (1 finger)", (180, 80, 220)
    elif zoom_active:
        label, color = "ZOOM  (open palm)", (200, 140, 0)
    elif scroll_active:
        label, color = "SCROLL  (2 fingers)", (60, 200, 80)
    else:
        label, color = "idle", (60, 60, 60)

    cv2.rectangle(frame, (10, 10), (260, 45), color, -1)
    cv2.putText(frame, label, (18, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

    cv2.putText(frame, f"FPS {fps:.0f}", (w - 90, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

    arrows = {
        "up": "^ UP", "down": "v DOWN",
        "left": "< LEFT", "right": "> RIGHT",
        "zoom_in": "+ ZOOM IN", "zoom_out": "- ZOOM OUT",
        "right_click": "[ RIGHT CLICK ]",
    }
    if direction:
        text = arrows.get(direction, direction)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)
        cv2.putText(frame, text, (w // 2 - tw // 2, h // 2 + th // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3, cv2.LINE_AA)

    cols_on = [(0, 220, 255), (60, 200, 80), (220, 100, 40), (200, 60, 200)]
    bx = w // 2 - (len(FINGER_NAMES) * 75) // 2
    for i, name in enumerate(FINGER_NAMES):
        col = cols_on[i] if finger_states[i] else (50, 50, 50)
        cv2.rectangle(frame, (bx, h - 45), (bx + 68, h - 15), col, -1)
        cv2.putText(frame, name, (bx + 4, h - 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 0, 0) if finger_states[i] else (150, 150, 150),
                    1, cv2.LINE_AA)
        bx += 75

    cv2.putText(frame, "P=pause  Q=quit", (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1, cv2.LINE_AA)


def main(mode: str = "camera"):
    # Wait for background preload (usually already done by the time user clicks)
    if not _preload_done.wait(timeout=30):
        print("Model load timed out.")
        return
    if _preload_error[0]:
        print(f"Model load failed: {_preload_error[0]}")
        return

    # Reuse the already-created instances — zero wait
    landmarker = _preloaded_landmarker[0]
    cap        = _preloaded_cap[0]

    pos_smoother   = PositionSmoother(alpha=0.9)   # near-instant response
    size_smoother  = EMA(0.2)
    mouse_smoother = PositionSmoother(alpha=MOUSE_SMOOTH)
    size_baseline  = None       # slow-moving reference size for zoom detection
    screen_w, screen_h = get_screen_size()

    prev_x = prev_y = None
    prev_time = None
    scroll_locked = False
    was_pointing  = False   # True when last frame was in mouse mode
    claw_ready    = True    # True = a right-click can fire on next claw
    mouse_active  = False
    direction = None
    dir_timer = 0.0
    paused = False
    clear_field_count = 0   # frames hand has been in the clear zone
    fps = 0.0
    frame_count  = 0
    display_tick = 0
    fps_timer    = time.perf_counter()
    start_time   = time.perf_counter()

    show_window = (mode == "camera")
    stop_event  = threading.Event()

    if show_window:
        print("AR Hand → Windows Input  |  P=pause  Q=quit")
        print("Open palm (3+ fingers) to start scrolling.\n")
    else:
        print("AR Hand Control running as background service.")
        print("Close the stop window or press Ctrl+C to quit.\n")
        _start_stop_widget(stop_event)

    while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # FPS counter
            frame_count += 1
            now = time.perf_counter()
            if now - fps_timer >= 0.5:
                fps = frame_count / (now - fps_timer)
                frame_count = 0
                fps_timer = now

            if direction and now - dir_timer > 0.5:
                direction = None

            # Run hand detection
            timestamp_ms = int((now - start_time) * 1000)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            lm = result.hand_landmarks[0] if result.hand_landmarks else None

            zoom_active   = False
            scroll_active = False
            finger_states = [False] * 4

            if lm:
                draw_skeleton(frame, lm, h, w)
                finger_states = get_extended_fingers(lm)
                zoom_active   = is_zoom_mode(lm)

                # Clear-field guard: require palm to be away from the face zone
                # and stable there for several frames before arming gestures.
                _, palm_cy = get_palm_center(lm)
                if palm_cy > CLEAR_ZONE_Y_MIN:
                    clear_field_count = min(clear_field_count + 1, CLEAR_FIELD_FRAMES)
                else:
                    clear_field_count = 0
                gesture_armed = (clear_field_count >= CLEAR_FIELD_FRAMES)

                # Mouse mode: only index finger extended → cursor follows fingertip.
                # Claw: fold index while in mouse mode → one right-click per fold.
                pointing_now = is_mouse_mode(lm)
                claw_now     = was_pointing and is_fist(lm)
                mouse_active = pointing_now or claw_now

                # Hysteresis: enter scroll mode on 2-finger gesture,
                # exit only when a clearly different gesture is made.
                # Mouse mode takes priority — skip scroll/zoom when mouse is active.
                if not mouse_active:
                    if is_scroll_mode(lm):
                        scroll_locked = True
                    elif zoom_active or is_fist(lm):
                        scroll_locked = False
                else:
                    scroll_locked = False
                scroll_active = scroll_locked and not zoom_active and not mouse_active

                raw_size = get_hand_size(lm)
                cur_size = size_smoother.update(raw_size)

                tx, ty = get_palm_center(lm)
                sx, sy = pos_smoother.update(tx, ty)

                # Raw delta — no EMA on velocity, position smoother is enough
                if prev_x is not None:
                    vx = sx - prev_x
                    vy = sy - prev_y
                else:
                    vx = vy = 0.0

                if not paused and gesture_armed:
                    # ── INDEX ONLY → Mouse pointer ─────────────────────────
                    if pointing_now:
                        was_pointing = True
                        claw_ready   = True
                        mx, my = mouse_smoother.update(lm[8].x, lm[8].y)
                        move_mouse(int(mx * screen_w), int(my * screen_h))

                    # ── CLAW (fold index while pointing) → Right-click ─────
                    elif claw_now:
                        if claw_ready:
                            right_click()
                            claw_ready = False
                            direction  = "right_click"
                            dir_timer  = now

                    # ── OPEN PALM → Zoom only ──────────────────────────────
                    elif zoom_active:
                        was_pointing = False
                        if size_baseline is None:
                            size_baseline = cur_size
                        size_baseline += ZOOM_BASELINE_RATE * (cur_size - size_baseline)
                        size_dev = cur_size - size_baseline

                        if abs(size_dev) > ZOOM_THRESHOLD:
                            zoom(size_dev * ZOOM_SPEED)
                            direction = "zoom_in" if size_dev > 0 else "zoom_out"
                            dir_timer = now

                    # ── INDEX + MIDDLE → Scroll X/Y only ──────────────────
                    elif scroll_active:
                        was_pointing  = False
                        size_baseline = None
                        dt = (now - prev_time) if prev_time else 0.0

                        # VERTICAL — pose based (no motion needed)
                        #   fingers flat  (high curl score) → UP
                        #   fingers bent  (low  curl score) → DOWN
                        curl = get_two_finger_curl(lm)
                        if curl > STRAIGHT_THRESHOLD:
                            scroll_vertical(SCROLL_POSE_SPEED * dt)
                            direction = "up"
                            dir_timer = now
                        elif curl < CURL_THRESHOLD:
                            scroll_vertical(-SCROLL_POSE_SPEED * dt)
                            direction = "down"
                            dir_timer = now

                        # HORIZONTAL — pose based (tilt fingers left or right)
                        tilt = get_horizontal_tilt(lm)
                        if tilt < -TILT_THRESHOLD:
                            scroll_horizontal(-SCROLL_POSE_SPEED * dt)   # tilt left on screen → scroll right
                            direction = "right"
                            dir_timer = now
                        elif tilt > TILT_THRESHOLD:
                            scroll_horizontal(SCROLL_POSE_SPEED * dt)    # tilt right on screen → scroll left
                            direction = "left"
                            dir_timer = now

                    else:
                        was_pointing  = False
                        size_baseline = None

                else:
                    # Not armed (hand near face) or paused — reset state
                    was_pointing  = False
                    claw_ready    = True
                    size_baseline = None

                prev_x, prev_y = sx, sy
                prev_time = now

            else:
                pos_smoother.reset()
                size_smoother.reset()
                mouse_smoother.reset()
                size_baseline = None
                scroll_locked = False
                was_pointing  = False
                claw_ready    = True
                mouse_active  = False
                clear_field_count = 0
                prev_x = prev_y = prev_time = None

            armed = lm is not None and clear_field_count >= CLEAR_FIELD_FRAMES

            if show_window:
                display_tick += 1
                if display_tick % 2 == 0:
                    draw_hud(frame, h, w, zoom_active, scroll_active, mouse_active, paused, direction, finger_states, fps, armed=armed)
                    cv2.imshow("AR Hand Control — Windows", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), 27):
                    break
                if key == ord('p'):
                    paused = not paused
            else:
                # Service mode — print live status, check stop widget
                if not armed and lm is not None:
                    label = "near face"
                elif mouse_active:
                    label = "MOUSE"
                else:
                    label = "ZOOM" if zoom_active else ("SCROLL" if scroll_active else "idle")
                print(f"\r[AR] {label:<10} | FPS {fps:4.0f} | {'PAUSED' if paused else 'active'}", end="", flush=True)
                if stop_event.is_set():
                    break
                time.sleep(0.001)

    cap.release()
    landmarker.close()
    if show_window:
        cv2.destroyAllWindows()
    else:
        print("\nService stopped.")


# ── Stop widget (service mode) ─────────────────────────────────────────────────

def _start_stop_widget(stop_event: threading.Event):
    """Launches a small tkinter stop button in a background thread."""
    def _run():
        import tkinter as tk
        root = tk.Tk()
        root.title("AR Hand Control")
        root.geometry("280x110")
        root.resizable(False, False)
        root.configure(bg="#0f0f1a")
        root.attributes("-topmost", True)

        tk.Label(root, text="Service running in background",
                 bg="#0f0f1a", fg="#aaaaaa",
                 font=("Segoe UI", 10)).pack(pady=(18, 6))

        tk.Button(root, text="■  Stop Service",
                  bg="#ff4444", fg="white", activebackground="#cc0000",
                  font=("Segoe UI", 11, "bold"), width=18, height=1,
                  relief="flat", cursor="hand2",
                  command=lambda: (stop_event.set(), root.destroy())
                  ).pack()

        root.protocol("WM_DELETE_WINDOW",
                      lambda: (stop_event.set(), root.destroy()))
        root.mainloop()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ── Launch menu ────────────────────────────────────────────────────────────────

def show_menu() -> str | None:
    """Tkinter launch menu — returns 'camera', 'service', or None if closed."""
    import tkinter as tk

    chosen = [None]

    root = tk.Tk()
    root.title("AR Hand Control")
    root.geometry("400x270")
    root.resizable(False, False)
    root.configure(bg="#0f0f1a")

    def pick(mode):
        chosen[0] = mode
        root.destroy()

    tk.Label(root, text="AR Hand Control",
             font=("Segoe UI", 18, "bold"),
             bg="#0f0f1a", fg="white").pack(pady=(24, 4))

    status_var = tk.StringVar(value="⏳  Loading model…")
    status_lbl = tk.Label(root, textvariable=status_var,
                          font=("Segoe UI", 9),
                          bg="#0f0f1a", fg="#888")
    status_lbl.pack(pady=(0, 14))

    def _poll_ready():
        if _preload_done.is_set():
            status_var.set("✓  Ready")
            status_lbl.config(fg="#6bcb77")
        else:
            root.after(200, _poll_ready)
    root.after(200, _poll_ready)

    # Camera button
    tk.Button(root, text="🎥   Play with Camera",
              font=("Segoe UI", 12, "bold"),
              bg="#4fc3f7", fg="#0f0f1a", activebackground="#29b6f6",
              width=26, height=2, relief="flat", cursor="hand2",
              command=lambda: pick("camera")).pack(pady=(0, 4))

    tk.Label(root, text="Live camera feed with hand skeleton overlay",
             font=("Segoe UI", 8), bg="#0f0f1a", fg="#555").pack()

    # Service button
    tk.Button(root, text="⚙️   Run as Background Service",
              font=("Segoe UI", 12, "bold"),
              bg="#6bcb77", fg="#0f0f1a", activebackground="#57bb65",
              width=26, height=2, relief="flat", cursor="hand2",
              command=lambda: pick("service")).pack(pady=(14, 4))

    tk.Label(root, text="No window — gesture control works system-wide",
             font=("Segoe UI", 8), bg="#0f0f1a", fg="#555").pack()

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return chosen[0]


if __name__ == "__main__":
    mode = show_menu()
    if mode:
        main(mode=mode)
