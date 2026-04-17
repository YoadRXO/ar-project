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
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from win_input import scroll_vertical, scroll_horizontal, zoom
from smoother import PositionSmoother, EMA  # EMA still used for size_smoother
from gesture import (
    get_extended_fingers, is_scroll_mode, is_zoom_mode, is_fist,
    get_palm_center, get_two_finger_center, get_hand_size, get_two_finger_curl,
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
STRAIGHT_THRESHOLD = 0.12   # curl score above this → fingers flat → scroll UP
CURL_THRESHOLD     = 0.03   # curl score below this → fingers bent  → scroll DOWN
SCROLL_POSE_SPEED  = 6      # scroll notches per second while holding pose
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


def draw_hud(frame, h, w, zoom_active, scroll_active, paused, direction, finger_states, fps):
    if paused:
        label, color = "PAUSED", (60, 60, 60)
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


def main():
    ensure_model()

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        # model_complexity is not exposed in tasks API — uses lite model via float16
    )

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FPS, 60)

    pos_smoother  = PositionSmoother(alpha=0.9)   # near-instant response
    size_smoother = EMA(0.2)
    size_baseline = None       # slow-moving reference size for zoom detection

    prev_x = prev_y = None
    prev_time = None
    accum_x = 0.0
    scroll_locked = False
    direction = None
    dir_timer = 0.0
    paused = False
    fps = 0.0
    frame_count  = 0
    display_tick = 0
    fps_timer    = time.perf_counter()
    start_time   = time.perf_counter()

    print("AR Hand → Windows Input  |  P=pause  Q=quit")
    print("Open palm (3+ fingers) to start scrolling.\n")

    with vision.HandLandmarker.create_from_options(options) as landmarker:
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

                # Hysteresis: enter scroll mode on 2-finger gesture,
                # exit only when a clearly different gesture is made
                if is_scroll_mode(lm):
                    scroll_locked = True
                elif zoom_active or is_fist(lm):
                    scroll_locked = False
                scroll_active = scroll_locked and not zoom_active

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

                if not paused:
                    # ── OPEN PALM → Zoom only ──────────────────────────────
                    if zoom_active:
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

                        # HORIZONTAL — motion based (move hand left/right)
                        accum_x += vx
                        if abs(accum_x) >= DEAD_ZONE * 3:
                            scroll_horizontal(accum_x * SCROLL_H_SPEED)
                            direction = "right" if accum_x > 0 else "left"
                            dir_timer = now
                            accum_x = 0.0

                    else:
                        size_baseline = None
                        accum_x = 0.0

                prev_x, prev_y = sx, sy
                prev_time = now

            else:
                pos_smoother.reset()
                size_smoother.reset()
                size_baseline = None
                scroll_locked = False
                accum_x = 0.0
                prev_x = prev_y = prev_time = None
                prev_x = prev_y = prev_size = None

            # Only redraw the window every 2 frames — display is the bottleneck
            display_tick += 1
            if display_tick % 2 == 0:
                draw_hud(frame, h, w, zoom_active, scroll_active, paused, direction, finger_states, fps)
                cv2.imshow("AR Hand Control — Windows", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            if key == ord('p'):
                paused = not paused
                print("Paused" if paused else "Resumed")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
