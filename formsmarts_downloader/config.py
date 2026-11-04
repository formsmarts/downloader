"""Plain-text configuration file (download directory, account ID).

The API key itself never lives here; see secrets_store.py. The
"key_storage" entry records the user's choice of how it is stored. Configs
written by versions before 1.1 don't have it (their key, if any, was saved
unprotected and gets migrated).
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

APP_NAME = "FormSmartsDownloader"
# Settings folder used by version 1.0 ("FormSmarts PDF Downloader").
LEGACY_APP_NAME = "FormSmartsPDFDownloader"

ACCOUNT_ID_RE = re.compile(r"^FSA-\d+$")

DEFAULTS = {
    "download_directory": str(Path.home() / "Documents" / "FormSmarts PDFs"),
    "account_id": None,
}


def _config_base() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming"))
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))


def config_dir() -> Path:
    path = _config_base() / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_dir(path)
    return path


def _migrate_legacy_dir(path: Path) -> None:
    """Move settings saved by version 1.0 into the current folder."""
    legacy = _config_base() / LEGACY_APP_NAME
    legacy_file = legacy / "config.json"
    target = path / "config.json"
    if target.exists() or not legacy_file.exists():
        return
    try:
        shutil.copy2(legacy_file, target)
        legacy_file.unlink()
        legacy.rmdir()  # only succeeds if nothing else is left in it
    except OSError:
        pass


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
