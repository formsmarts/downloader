"""Tkinter desktop UI for FormSmarts Downloader.

Uses the same config file, OS secret store and download logic as the CLI,
so settings saved from either one are shared.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

from . import __version__
from . import config as config_mod
from . import datefield
from . import secrets_store

APP_TITLE = "FormSmarts Downloader"
POLL_MS = 100
PAD = 8


ASSETS = Path(__file__).resolve().parent / "assets"
ACCOUNT_URL = "https://formsmarts.com/account/view#overview"
API_KEY_URL = "https://formsmarts.com/account/view#security-settings"


def _check_date(widget, label: str) -> date:
    d = widget.get_date()
    if d is None:
        raise ValueError(
            "{} isn't a valid date. Enter it like this: {}".format(label, datefield.example())
        )
    return d


def _link(parent, text: str, url: str) -> ttk.Label:
    """A label that opens `url` in the browser when clicked."""
    try:
        color = "systemLinkColor" if sys.platform == "darwin" else "#0066cc"
        parent.winfo_rgb(color)
    except tk.TclError:
        color = "#0066cc"
    label = ttk.Label(parent, text=text, foreground=color, cursor="hand2")
    label.bind("<Button-1>", lambda _e: webbrowser.open(url))
    return label


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 - opening a local folder
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=PAD * 2)
        self.master = master
        self.cfg = config_mod.load_config()
        self.events = queue.Queue()
        self.worker = None
        self.cancel_event = threading.Event()
        self.last_output_dir = None
        self.counts = {}

        self.dir_var = tk.StringVar(value=self.cfg["download_directory"])
        self.account_var = tk.StringVar(value=self.cfg.get("account_id") or "")
        self.key_var = tk.StringVar()
        self.key_placeholder_var = tk.StringVar()  # shown in the field when a key is saved
        self.key_status_var = tk.StringVar()
        self.session_key = None  # API key kept in memory for this session only
        self.busy = False
        self.mode_options = secrets_store.mode_labels()
        default_mode = (
            secrets_store.MODE_PROTECTED
            if len(self.mode_options) > 1 and "key_storage" not in self.cfg
            else secrets_store.effective_mode(self.cfg)
        )
        self.mode_var = tk.StringVar(value=default_mode)
        self.form_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")

        self._build()
        self._refresh_key_status()
        self.grid(sticky="nsew")
        self.after(200, self._migrate_legacy)
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

    # ------------------------------------------------------------------ layout

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Settings
        settings = ttk.LabelFrame(self, text="Settings", padding=PAD)
        settings.grid(row=0, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Download folder").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(settings, textvariable=self.dir_var).grid(
            row=0, column=1, sticky="ew", padx=PAD, pady=2
        )
        ttk.Button(settings, text="Browse…", command=self._browse).grid(row=0, column=2, pady=2)

        _link(settings, "Account ID", ACCOUNT_URL).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(settings, textvariable=self.account_var, width=20).grid(
            row=1, column=1, sticky="w", padx=PAD, pady=2
        )

        _link(settings, "API key", API_KEY_URL).grid(row=2, column=0, sticky="w", pady=2)
        self.key_entry = ttk.Entry(settings, textvariable=self.key_var, show="•")
        self.key_entry.grid(row=2, column=1, sticky="ew", padx=PAD, pady=2)
        for event in ("<FocusIn>", "<FocusOut>", "<Configure>"):
            self.key_entry.bind(event, self._refresh_key_status, add="+")
        self.key_var.trace_add("write", lambda *_: self._refresh_key_status())
        self.account_var.trace_add("write", lambda *_: self._refresh_key_status())

        storage = ttk.Frame(settings)
        storage.grid(row=3, column=1, columnspan=2, sticky="w", padx=PAD, pady=(4, 0))
        if len(self.mode_options) > 1:
            for mode, label in self.mode_options:
                ttk.Radiobutton(
                    storage, text=label, value=mode, variable=self.mode_var,
                    command=self._refresh_key_status,
                ).pack(anchor="w")
        else:
            ttk.Label(
                storage,
                text="Your API key is kept in memory only and asked for each session.",
                foreground="gray",
            ).pack(anchor="w")

        ttk.Label(settings, textvariable=self.key_status_var, foreground="gray").grid(
            row=4, column=1, sticky="w", padx=PAD, pady=(4, 0)
        )
        self.save_btn = ttk.Button(settings, text="Save settings", command=self._save_settings)
        self.save_btn.grid(row=4, column=2, sticky="e", pady=(4, 0))

        # Download
        dl = ttk.LabelFrame(self, text="Download", padding=PAD)
        dl.grid(row=1, column=0, sticky="ew", pady=(PAD, 0))
        dl.columnconfigure(5, weight=1)

        ttk.Label(dl, text="Form ID").grid(row=0, column=0, sticky="w")
        self.form_entry = ttk.Entry(dl, textvariable=self.form_var, width=8)
        self.form_entry.grid(row=0, column=1, sticky="w", padx=(4, PAD * 2))
        today = date.today()
        ttk.Label(dl, text="From").grid(row=0, column=2, sticky="w")
        self.start_field = datefield.DateField(dl, today.replace(day=1))
        self.start_field.grid(row=0, column=3, sticky="w", padx=(4, PAD * 2))
        ttk.Label(dl, text="To").grid(row=0, column=4, sticky="w")
        self.end_field = datefield.DateField(dl, today)
        self.end_field.grid(row=0, column=5, sticky="w", padx=(4, 0))
        ttk.Label(dl, text="Both dates are included.", foreground="gray").grid(
            row=1, column=0, columnspan=6, sticky="w", pady=(2, 0)
        )

        buttons = ttk.Frame(dl)
        buttons.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(PAD, 0))
        self.download_btn = ttk.Button(buttons, text="Download", command=self._start)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(buttons, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=PAD)
        self.open_btn = ttk.Button(
            buttons, text="Open folder", command=self._open_output, state="disabled"
        )
        self.open_btn.pack(side="right")

        # Progress / log
        out = ttk.Frame(self)
        out.grid(row=2, column=0, sticky="nsew", pady=(PAD, 0))
        out.columnconfigure(0, weight=1)
        out.rowconfigure(1, weight=1)
        self.progress = ttk.Progressbar(out, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew")
        self.log = ScrolledText(out, height=14, wrap="word", state="disabled")
        self.log.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        ttk.Label(out, textvariable=self.status_var).grid(row=2, column=0, sticky="w", pady=(4, 0))

        self.form_entry.focus_set()

    # ---------------------------------------------------------------- settings

    def _browse(self):
        chosen = filedialog.askdirectory(
            initialdir=self.dir_var.get() or str(Path.home()), mustexist=False
        )
        if chosen:
            self.dir_var.set(chosen)

    def _key_is_saved(self) -> bool:
        account = config_mod.normalize_account_id(self.account_var.get())
        return (
            bool(account)
            and account == self.cfg.get("account_id")
            and secrets_store.effective_mode(self.cfg) == secrets_store.MODE_PROTECTED
            and secrets_store.has_saved_key(account)
        )

    def _show_key_placeholder(self, show: bool):
        """When a key is saved, the empty field is filled with dots so users
        know they don't need to enter it again. Typing replaces the key."""
        if show:
            font = tkfont.nametofont("TkTextFont")
            width = max(self.key_entry.winfo_width() - 12, 0)
            self.key_placeholder_var.set("\u2022" * max(width // max(font.measure("\u2022"), 1), 14))
            self.key_entry.configure(textvariable=self.key_placeholder_var, show="")
        elif str(self.key_entry.cget("textvariable")) != str(self.key_var):
            self.key_entry.configure(textvariable=self.key_var, show="•")

    def _refresh_key_status(self, *_):
        # Never display the full key: only its last characters (mask_key).
        mask = secrets_store.mask_key
        protected = self.mode_var.get() == secrets_store.MODE_PROTECTED
        typed = self.key_var.get().strip()
        saved = self._key_is_saved()
        focused = self.focus_get() is self.key_entry
        self._show_key_placeholder(saved and not typed and not focused)

        if typed:
            self.key_status_var.set(
                "Key entered: {}{}".format(mask(typed), "  (click Save settings)" if protected else "")
            )
        elif saved:
            self.key_status_var.set("A key is saved, it's unlocked when you press Download.")
        elif self.session_key and config_mod.normalize_account_id(
            self.account_var.get()
        ) == self.cfg.get("account_id"):
            self.key_status_var.set(
                "Key {} kept in memory for this session only.".format(mask(self.session_key))
            )
        elif protected:
            self.key_status_var.set("Enter your API key and click Save settings.")
        else:
            self.key_status_var.set("You'll be asked for the key when downloading.")

    def _run_bg(self, fn, done):
        """Run fn() off the UI thread (OS verification prompts block), then
        call done(result, error) on the UI thread."""
        box = {}

        def target():
            try:
                box["result"] = fn()
            except Exception as e:  # passed to `done`
                box["error"] = e

        thread = threading.Thread(target=target, daemon=True)
        self._set_busy(True)
        thread.start()

        def poll():
            if thread.is_alive():
                self.after(POLL_MS, poll)
                return
            self._set_busy(False)
            done(box.get("result"), box.get("error"))

        self.after(POLL_MS, poll)

    def _set_busy(self, busy: bool):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.save_btn.configure(state=state)
        if not (self.worker and self.worker.is_alive()):
            self.download_btn.configure(state=state)

    def _validate_settings(self):
        directory = self.dir_var.get().strip()
        account = config_mod.normalize_account_id(self.account_var.get())
        self.account_var.set(account)
        if not directory:
            raise ValueError("Please choose a download folder.")
        if not account:
            raise ValueError("Please enter your FormSmarts Account ID.")
        if not config_mod.ACCOUNT_ID_RE.match(account):
            raise ValueError(
                "'{}' doesn't look like a valid Account ID "
                "(expected format: FSA-123456).".format(account)
            )
        return directory, account

    def _save_basic_settings(self) -> bool:
        """Save folder + account (not the key). Returns False on bad input."""
        try:
            directory, account = self._validate_settings()
            Path(directory).mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as e:
            messagebox.showerror(APP_TITLE, str(e), parent=self.master)
            return False
        previous = self.cfg.get("account_id")
        if previous and previous != account:
            secrets_store.delete_api_key(previous)
            self.session_key = None
        self.cfg["download_directory"] = directory
        self.cfg["account_id"] = account
        self.cfg.setdefault("key_storage", secrets_store.MODE_NONE)
        config_mod.save_config(self.cfg)
        return True

    def _save_settings(self):
        if self.busy or not self._save_basic_settings():
            return
        account = self.cfg["account_id"]
        typed = self.key_var.get().strip()
        mode = self.mode_var.get()

        if mode == secrets_store.MODE_NONE:
            secrets_store.delete_api_key(account)
            if typed:
                self.session_key = typed
                self.key_var.set("")
            self._set_mode(secrets_store.MODE_NONE)
            messagebox.showinfo(APP_TITLE, "Settings saved.", parent=self.master)
            return

        key = typed or self.session_key
        if not key:
            if secrets_store.has_saved_key(account):
                self._set_mode(secrets_store.MODE_PROTECTED)
                messagebox.showinfo(APP_TITLE, "Settings saved.", parent=self.master)
            else:
                messagebox.showerror(
                    APP_TITLE, "Please enter your API key to save it.", parent=self.master
                )
            return
        self._save_protected(account, key)

    def _save_protected(self, account, key, after=None):
        self.key_status_var.set(
            "Verify with {} to save the key…".format(secrets_store.protection_name())
        )

        def done(_, error):
            if error:
                self._set_mode(secrets_store.MODE_NONE)
                self.session_key = key
                messagebox.showerror(
                    APP_TITLE,
                    "The API key could not be saved:\n{}\n\n"
                    "It will be kept in memory for this session only.".format(error),
                    parent=self.master,
                )
            else:
                self.session_key = key
                self.key_var.set("")
                self._set_mode(secrets_store.MODE_PROTECTED)
                if after is None:
                    messagebox.showinfo(APP_TITLE, "Settings saved.", parent=self.master)
            if after:
                after()

        self._run_bg(lambda: secrets_store.save_api_key(account, key), done)

    def _set_mode(self, mode):
        self.mode_var.set(mode)
        self.cfg["key_storage"] = mode
        config_mod.save_config(self.cfg)
        self._refresh_key_status()

    def _migrate_legacy(self):
        """Version 1.0 saved the key unprotected in the OS credential
        store. Move it out of there (into protected storage if possible)."""
        account = self.cfg.get("account_id")
        if "key_storage" in self.cfg or not account:
            return
        key = secrets_store.take_legacy_key(account)
        if not key:
            self._set_mode(secrets_store.effective_mode(self.cfg))
            return
        self.session_key = key
        name = secrets_store.protection_name()
        if name and messagebox.askyesno(
            APP_TITLE,
            "An earlier version saved your API key without protection. It has "
            "been removed from there.\n\nSave it again, protected by {}?".format(name),
            parent=self.master,
        ):
            self._save_protected(account, key)
        else:
            self._set_mode(secrets_store.MODE_NONE)

    def _with_api_key(self, account, proceed):
        """Get the API key (typed, in memory, saved, or asked for) and call
        proceed(key)."""
        key = self.key_var.get().strip() or self.session_key
        if key:
            proceed(key)
            return
        if (
            secrets_store.effective_mode(self.cfg) == secrets_store.MODE_PROTECTED
            and secrets_store.has_saved_key(account)
        ):
            self.status_var.set(
                "Verify with {} to unlock your API key…".format(secrets_store.protection_name())
            )

            def done(result, error):
                self.status_var.set("Ready.")
                if result:
                    self.session_key = result
                    self._refresh_key_status()
                    proceed(result)
                elif not isinstance(error, secrets_store.UnlockCancelled):
                    if error:
                        messagebox.showerror(
                            APP_TITLE,
                            "Couldn't unlock the saved API key:\n{}".format(error),
                            parent=self.master,
                        )
                    self._ask_key(proceed)

            self._run_bg(lambda: secrets_store.load_api_key(account), done)
            return
        self._ask_key(proceed)

    def _ask_key(self, proceed):
        key = simpledialog.askstring(
            APP_TITLE, "FormSmarts API key:", show="•", parent=self.master
        )
        if key and key.strip():
            self.session_key = key.strip()
            self._refresh_key_status()
            proceed(self.session_key)

    # ---------------------------------------------------------------- download

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            from . import downloader
        except ImportError as e:
            messagebox.showerror(APP_TITLE, str(e), parent=self.master)
            return

        if self.busy or not self._save_basic_settings():
            return
        account = self.cfg["account_id"]

        form_id = self.form_var.get().strip()
        try:
            if not form_id:
                raise ValueError("Please enter a Form ID.")
            start_date = _check_date(self.start_field, "The start date")
            end_date = _check_date(self.end_field, "The end date")
            if end_date < start_date:
                raise ValueError("The end date cannot be before the start date.")
            output_dir = downloader.build_output_dir(
                self.cfg["download_directory"], form_id, start_date, end_date
            )
        except (ValueError, OSError) as e:
            messagebox.showerror(APP_TITLE, str(e), parent=self.master)
            return

        self._with_api_key(
            account,
            lambda api_key: self._begin_download(
                downloader, account, api_key, form_id, start_date, end_date, output_dir
            ),
        )

    def _begin_download(self, downloader, account, api_key, form_id, start_date, end_date,
                        output_dir):
        self.last_output_dir = output_dir
        self.counts = {"downloaded": 0, "skipped": 0, "failed": 0}
        self.cancel_event.clear()
        self._clear_log()
        self._log("Saving PDFs to: {}".format(output_dir))
        self._set_running(True)

        def progress(status, ref, extra):
            self.events.put((status, ref, extra))

        def work():
            error = None
            try:
                downloader.download_submissions(
                    account, api_key, form_id, start_date, end_date, output_dir,
                    progress_cb=progress, cancel_event=self.cancel_event,
                )
            except downloader.AuthenticationError:
                error = "Authentication failed. Check your Account ID and API key."
                self.events.put(("auth_failed", None, None))
            except (downloader.APIRequestError, downloader.APIError) as e:
                error = "FormSmarts API error: {}".format(e)
            except Exception as e:  # network errors, timeouts, etc.
                error = "Couldn't reach FormSmarts: {}".format(e)
            self.events.put(("done", None, error))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.after(POLL_MS, self._poll)

    def _cancel(self):
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled")
        self.status_var.set("Cancelling after the current file…")

    def _poll(self):
        try:
            while True:
                status, ref, extra = self.events.get_nowait()
                if status == "ok":
                    self.counts["downloaded"] += 1
                    self._log("Downloaded entry {} → {}".format(ref, extra.name))
                elif status == "skip":
                    self.counts["skipped"] += 1
                    self._log("Already downloaded, skipped entry {}".format(ref))
                elif status == "error":
                    self.counts["failed"] += 1
                    self._log("FAILED entry {}: {}".format(ref, extra))
                elif status == "auth_failed":
                    self.session_key = None
                elif status == "done":
                    self._finish(extra)
                    return
        except queue.Empty:
            pass
        self.status_var.set(self._summary("Working…"))
        self.after(POLL_MS, self._poll)

    def _summary(self, prefix):
        return "{} Downloaded {}, skipped {}, failed {}.".format(
            prefix, self.counts["downloaded"], self.counts["skipped"], self.counts["failed"]
        )

    def _finish(self, error):
        self._set_running(False)
        if error:
            self._log("")
            self._log(error)
            prefix = "Stopped with an error."
        elif self.cancel_event.is_set():
            prefix = "Cancelled."
        else:
            prefix = "Done."
        summary = self._summary(prefix)
        self._log("")
        self._log(summary)
        self.status_var.set(summary)
        if error:
            messagebox.showerror(APP_TITLE, error, parent=self.master)

    def _set_running(self, running: bool):
        self.download_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.open_btn.configure(state="normal" if self.last_output_dir else "disabled")
        if running:
            self.progress.start(15)
        else:
            self.progress.stop()

    def _open_output(self):
        if self.last_output_dir:
            _open_folder(self.last_output_dir)

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _log(self, line: str):
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(
                APP_TITLE, "A download is in progress. Quit anyway?", parent=self.master
            ):
                return
            self.cancel_event.set()
        self.master.destroy()


def _enable_windows_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _set_window_icon(root: tk.Tk):
    try:
        if sys.platform == "win32":
            root.iconbitmap(default=str(ASSETS / "app_icon.ico"))
        elif sys.platform != "darwin":  # macOS uses the app bundle's icon
            root.iconphoto(True, tk.PhotoImage(file=str(ASSETS / "app_icon.png")))
    except (tk.TclError, OSError):
        pass


def main():
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    _set_window_icon(root)
    root.title("{} {}".format(APP_TITLE, __version__))
    root.minsize(560, 480)
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
