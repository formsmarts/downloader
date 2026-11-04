"""Native Windows date control (SysDateTimePick32) embedded in a Tk frame.

It displays and accepts dates in the user's regional format (Control Panel
> Region) and has the standard drop-down calendar.
"""

import ctypes
import tkinter as tk
from ctypes import wintypes
from datetime import date

ICC_DATE_CLASSES = 0x00000100
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_TABSTOP = 0x00010000
DTS_SHORTDATECENTURYFORMAT = 0x000C
DTM_GETSYSTEMTIME = 0x1001
DTM_SETSYSTEMTIME = 0x1002
GDT_VALID = 0
WM_SETFONT = 0x0030
LOCALE_SSHORTDATE = 0x0000001F

user32 = ctypes.windll.user32
comctl32 = ctypes.windll.comctl32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.MoveWindow.argtypes = [
    wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL
]
gdi32.CreateFontW.restype = wintypes.HFONT


class _INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("dwICC", wintypes.DWORD)]


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        (name, wintypes.WORD)
        for name in ("wYear", "wMonth", "wDayOfWeek", "wDay",
                     "wHour", "wMinute", "wSecond", "wMilliseconds")
    ]


_initialized = False


def _init():
    global _initialized
    if not _initialized:
        icc = _INITCOMMONCONTROLSEX(ctypes.sizeof(_INITCOMMONCONTROLSEX), ICC_DATE_CLASSES)
        if not comctl32.InitCommonControlsEx(ctypes.byref(icc)):
            raise OSError("InitCommonControlsEx failed")
        _initialized = True


def short_date_pattern() -> str:
    """The user's short date pattern, e.g. 'M/d/yyyy' or 'dd.MM.yyyy'."""
    buf = ctypes.create_unicode_buffer(80)
    if kernel32.GetLocaleInfoEx(None, LOCALE_SSHORTDATE, buf, len(buf)):
        return buf.value
    return ""


class DatePicker(tk.Frame):
    """A Tk frame hosting the native date control."""

    def __init__(self, master, initial: date, font):
        width = font.measure("00/00/0000") + 48
        height = font.metrics("linespace") + 10
        super().__init__(master, width=width, height=height)
        self.pack_propagate(False)
        self.grid_propagate(False)
        _init()
        self.update_idletasks()
        self._hwnd = user32.CreateWindowExW(
            0, "SysDateTimePick32", None,
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | DTS_SHORTDATECENTURYFORMAT,
            0, 0, width, height, self.winfo_id(), None, None, None,
        )
        if not self._hwnd:
            raise OSError("Couldn't create the date control")
        # Match Tk's font: Tk sizes are points (>0) or pixels (<0);
        # CreateFontW takes a negative character height in pixels.
        size = font.actual("size")
        px = -size if size < 0 else round(size * self.winfo_fpixels("1i") / 72)
        self._font = gdi32.CreateFontW(
            -px, 0, 0, 0, 400, 0, 0, 0,
            1,  # DEFAULT_CHARSET
            0, 0,
            5,  # CLEARTYPE_QUALITY
            0, font.actual("family"),
        )
        if self._font:
            user32.SendMessageW(self._hwnd, WM_SETFONT, self._font, 1)
        self.set_date(initial)
        self.bind("<Configure>", self._resize)
        self.bind("<Destroy>", self._destroy)

    def _resize(self, event):
        user32.MoveWindow(self._hwnd, 0, 0, event.width, event.height, True)

    def _destroy(self, _event):
        if self._font:
            gdi32.DeleteObject(self._font)
            self._font = None

    def get_date(self) -> date:
        st = _SYSTEMTIME()
        user32.SendMessageW(self._hwnd, DTM_GETSYSTEMTIME, 0, ctypes.addressof(st))
        return date(st.wYear, st.wMonth, st.wDay)

    def set_date(self, d: date) -> None:
        st = _SYSTEMTIME(d.year, d.month, 0, d.day, 12, 0, 0, 0)
        user32.SendMessageW(self._hwnd, DTM_SETSYSTEMTIME, GDT_VALID, ctypes.addressof(st))
