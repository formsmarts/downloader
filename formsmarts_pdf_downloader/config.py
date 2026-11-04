"""Plain-text configuration file (download directory, account ID).

The API key itself never lives here. It is only ever written to the OS
secret store (see secrets_store.py); if none is available it is never
persisted, and the user is prompted for it every run.
"""

import json
import os
import sys
from pathlib import Path

APP_NAME = "FormSmartsPDFDownloader"

DEFAULTS = {
    "download_directory": str(Path.home() / "Documents" / "FormSmarts PDFs"),
    "account_id": None,
}


def config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    path = config_path()
    cfg = DEFAULTS.copy()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def save_config(cfg: dict) -> None:
    path = config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    if sys.platform != "win32":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
