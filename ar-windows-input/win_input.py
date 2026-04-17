"""
Windows input injection via mouse_event (user32.dll).
Works system-wide — scrolls whatever window is under the cursor.
"""
import ctypes

_user32 = ctypes.windll.user32

MOUSEEVENTF_WHEEL  = 0x0800   # vertical scroll
MOUSEEVENTF_HWHEEL = 0x1000   # horizontal scroll
VK_CONTROL         = 0x11
KEYEVENTF_KEYUP    = 0x0002

# One Windows scroll notch = 120 units
_NOTCH = 120


def _mouse_event(flags: int, data: int) -> None:
    # mouseData must be a signed DWORD; ctypes.c_long handles the sign correctly
    _user32.mouse_event(flags, 0, 0, ctypes.c_long(data), 0)


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
