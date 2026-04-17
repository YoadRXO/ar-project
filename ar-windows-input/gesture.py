"""
Gesture detection — mirrors the JS logic from the browser app.
All landmark coordinates are MediaPipe normalized [0, 1].
"""
import math

# (tip_index, mcp_index) for index/middle/ring/pinky
_FINGERS = [(8, 5), (12, 9), (16, 13), (20, 17)]

FINGER_NAMES = ["Index", "Middle", "Ring", "Pinky"]


def get_extended_fingers(lm) -> list[bool]:
    """Returns [index, middle, ring, pinky] — True = finger is extended."""
    return [lm[tip].y < lm[mcp].y for tip, mcp in _FINGERS]


def count_extended(lm) -> int:
    return sum(get_extended_fingers(lm))


def is_fist(lm) -> bool:
    return count_extended(lm) == 0


def is_zoom_mode(lm) -> bool:
    """All 4 fingers extended (open palm) → zoom only."""
    s = get_extended_fingers(lm)
    return all(s)


def is_scroll_mode(lm) -> bool:
    """Index + middle clearly up — ring/pinky state is ignored for robustness."""
    # Use a stricter margin than get_extended_fingers to reduce flicker:
    # tip must be clearly above the PIP joint (not just MCP)
    index_up  = lm[8].y  < lm[6].y  - 0.02   # index tip above index PIP
    middle_up = lm[12].y < lm[10].y - 0.02    # middle tip above middle PIP
    ring_down = lm[16].y > lm[13].y            # ring tip below ring MCP
    return index_up and middle_up and ring_down


def get_two_finger_center(lm):
    """Midpoint of index + middle fingertips — natural anchor for 2-finger scroll."""
    return (
        (lm[8].x + lm[12].x) / 2,
        (lm[8].y + lm[12].y) / 2,
    )


def get_horizontal_tilt(lm) -> float:
    """
    Horizontal tilt of index + middle fingers.
    Negative = tips lean LEFT  on the displayed (mirrored) frame → scroll RIGHT
    Positive = tips lean RIGHT on the displayed (mirrored) frame → scroll LEFT
    (frame is flipped before MediaPipe, so x-axis is already selfie-mirrored)
    """
    index_tilt  = lm[8].x  - lm[5].x    # index  tip.x  - MCP.x
    middle_tilt = lm[12].x - lm[9].x    # middle tip.x  - MCP.x
    return (index_tilt + middle_tilt) / 2


def get_two_finger_curl(lm) -> float:
    """
    Curl score for index + middle fingers.
    High positive  = fingers straight/flat  → scroll UP
    Near zero/neg  = fingers bent ~90°      → scroll DOWN
    Measured as average (mcp.y - tip.y): positive = tip above knuckle.
    """
    index_ext  = lm[5].y  - lm[8].y   # index  MCP.y - tip.y
    middle_ext = lm[9].y  - lm[12].y  # middle MCP.y - tip.y
    return (index_ext + middle_ext) / 2


def get_palm_center(lm):
    """Midpoint between wrist (0) and middle-finger MCP (9)."""
    return (
        (lm[0].x + lm[9].x) / 2,
        (lm[0].y + lm[9].y) / 2,
    )


def get_hand_size(lm) -> float:
    """Apparent 2-D size of hand — proxy for Z-depth (larger = closer)."""
    dx = lm[0].x - lm[9].x
    dy = lm[0].y - lm[9].y
    return math.sqrt(dx * dx + dy * dy)


# MediaPipe hand skeleton for OpenCV drawing
CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),            # thumb
    (0,5),(5,6),(6,7),(7,8),            # index
    (0,9),(9,10),(10,11),(11,12),       # middle
    (0,13),(13,14),(14,15),(15,16),     # ring
    (0,17),(17,18),(18,19),(19,20),     # pinky
    (5,9),(9,13),(13,17),               # palm
]

FINGER_COLORS_BGR = [
    (0, 100, 255),   # thumb    — red-orange
    (0, 220, 255),   # index    — yellow
    (60, 200, 80),   # middle   — green
    (220, 100, 40),  # ring     — blue
    (200, 60, 200),  # pinky    — purple
    (180, 180, 180), # palm     — grey
]

FINGER_CONNECTIONS = [
    [(0,1),(1,2),(2,3),(3,4)],
    [(0,5),(5,6),(6,7),(7,8)],
    [(0,9),(9,10),(10,11),(11,12)],
    [(0,13),(13,14),(14,15),(15,16)],
    [(0,17),(17,18),(18,19),(19,20)],
    [(5,9),(9,13),(13,17)],
]
