"""
Windows input injection via mouse_event / SetCursorPos (user32.dll).
Works system-wide — scrolls/clicks whatever window is under the cursor.
"""
import ctypes

_user32 = ctypes.windll.user32

MOUSEEVENTF_WHEEL      = 0x0800
MOUSEEVENTF_HWHEEL     = 0x1000
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
VK_CONTROL             = 0x11
KEYEVENTF_KEYUP        = 0x0002

_NOTCH = 120


def _mouse_event(flags: int, data: int) -> None:
    _user32.mouse_event(flags, 0, 0, ctypes.c_long(data), 0)


def get_screen_size() -> tuple[int, int]:
    """Return (width, height) of the primary monitor in pixels."""
    return _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)


def move_mouse(x: int, y: int) -> None:
    """Move cursor to absolute screen pixel position."""
    _user32.SetCursorPos(x, y)


def left_click() -> None:
    """Fire a left-click at the current cursor position."""
    _mouse_event(MOUSEEVENTF_LEFTDOWN, 0)
    _mouse_event(MOUSEEVENTF_LEFTUP,   0)


def right_click() -> None:
    """Fire a right-click at the current cursor position."""
    _mouse_event(MOUSEEVENTF_RIGHTDOWN, 0)
    _mouse_event(MOUSEEVENTF_RIGHTUP,   0)


def scroll_vertical(delta: float) -> None:
    """delta > 0 = up, delta < 0 = down"""
    amount = int(delta * _NOTCH)
    if amount != 0:
        _mouse_event(MOUSEEVENTF_WHEEL, amount)


def scroll_horizontal(delta: float) -> None:
    """delta > 0 = right, delta < 0 = left"""
    amount = int(delta * _NOTCH)
    if amount != 0:
        _mouse_event(MOUSEEVENTF_HWHEEL, amount)


def zoom(delta: float) -> None:
    """Ctrl + vertical scroll = browser zoom. delta > 0 = in, < 0 = out"""
    amount = int(delta * _NOTCH)
    if amount != 0:
        _user32.keybd_event(VK_CONTROL, 0, 0, 0)
        _mouse_event(MOUSEEVENTF_WHEEL, amount)
        _user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
