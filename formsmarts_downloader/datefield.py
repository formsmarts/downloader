"""Date input in the user's regional format, with the OS's native picker.

  Windows: the native Windows date control (regional format + drop-down
           calendar).
  macOS:   a text field in the Mac's regional format, with a button that
           opens the native macOS calendar.
  Other / fallback: a text field in the regional format.

Dates are only converted to ISO (YYYY-MM-DD) when talking to the API.
"""

import re
import sys
import tkinter as tk
from datetime import date
from tkinter import font as tkfont
from tkinter import ttk


# ------------------------------------------------- regional format (fallback)


def _fallback_order_and_sep():
    """('dmy' | 'mdy' | 'ymd', separator) from the OS short date pattern."""
    pattern = ""
    if sys.platform == "win32":
        try:
            from . import _win_dates

            pattern = _win_dates.short_date_pattern()
        except Exception:
            pattern = ""
    else:
        try:
            import locale

            locale.setlocale(locale.LC_TIME, "")
            pattern = locale.nl_langinfo(locale.D_FMT)
            pattern = pattern.replace("%d", "d").replace("%m", "M").replace("%Y", "y").replace("%y", "y")
        except Exception:
            pattern = ""
    letters = "".join(c for c in pattern.lower() if c in "dmy")
    order = "".join(dict.fromkeys(letters))  # unique, in order
    if order not in ("dmy", "mdy", "ymd"):
        return "ymd", "-"
    sep = next((c for c in pattern if not c.isalpha() and not c.isspace()), "/")
    return order, sep


class _RegionalFormat:
    def __init__(self):
        self._mac = None
        if sys.platform == "darwin":
            try:
                from . import _mac_dates

                self._mac = _mac_dates
            except Exception:
                self._mac = None
        if self._mac is None:
            self.order, self.sep = _fallback_order_and_sep()

    def format(self, d: date) -> str:
        if self._mac:
            return self._mac.format_date(d)
        parts = {"d": "{:02d}".format(d.day), "m": "{:02d}".format(d.month), "y": str(d.year)}
        return self.sep.join(parts[c] for c in self.order)

    def parse(self, text: str):
        text = text.strip()
        if not text:
            return None
        iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        if iso:  # always accept ISO too
            return _make_date(*map(int, iso.groups()))
        if self._mac:
            return self._mac.parse_date(text)
        nums = re.findall(r"\d+", text)
        if len(nums) != 3:
            return None
        values = dict(zip(self.order, map(int, nums)))
        year = values["y"] + 2000 if values["y"] < 100 else values["y"]
        return _make_date(year, values["m"], values["d"])


def _make_date(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


_format = None


def regional_format() -> _RegionalFormat:
    global _format
    if _format is None:
        _format = _RegionalFormat()
    return _format


def example() -> str:
    """Today's date in the user's format, for messages."""
    return regional_format().format(date.today())


# ----------------------------------------------------------------- widgets


class _TextDateField(ttk.Frame):
    """Text field in the regional format, plus the native macOS calendar."""

    def __init__(self, master, initial: date):
        super().__init__(master)
        self._fmt = regional_format()
        self.var = tk.StringVar(value=self._fmt.format(initial) if initial else "")
        entry = ttk.Entry(self, textvariable=self.var, width=12)
        entry.pack(side="left")
        entry.bind("<FocusOut>", self._normalize)
        if sys.platform == "darwin" and self._fmt._mac:
            self._button = ttk.Button(self, text="▾", width=2, command=self._open_picker)
            self._button.pack(side="left", padx=(2, 0))

    def _normalize(self, _event=None):
        d = self._fmt.parse(self.var.get())
        if d:
            self.var.set(self._fmt.format(d))

    def _open_picker(self):
        from . import _mac_dates

        initial = self._fmt.parse(self.var.get()) or date.today()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 4
        _mac_dates.show_picker(initial, x, y, lambda d: self.var.set(self._fmt.format(d)))

    def get_date(self):
        """The entered date, or None if it isn't a valid date."""
        return self._fmt.parse(self.var.get())


def DateField(master, initial: date):
    """A date input widget with get_date() -> date | None."""
    if sys.platform == "win32":
        try:
            from . import _win_dates

            return _win_dates.DatePicker(master, initial, tkfont.nametofont("TkDefaultFont"))
        except Exception:
            pass  # fall back to the text field
    return _TextDateField(master, initial)
