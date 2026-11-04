"""Command-line interface: interactive PDF download + configuration wizard."""

import argparse
import getpass
import sys
from datetime import date, datetime
from pathlib import Path

from . import config as config_mod
from . import secrets_store


def _prompt_date(label: str, default: date = None) -> date:
    suffix = " [{}]".format(default.isoformat()) if default else ""
    while True:
        raw = input("{}{}: ".format(label, suffix)).strip()
        if not raw and default:
            return default
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            print("Please enter a date in YYYY-MM-DD format (e.g. 2026-01-31).")


def _parse_date_arg(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        print("Invalid date '{}', expected YYYY-MM-DD.".format(raw))
        sys.exit(1)


def _choose_storage(cfg: dict) -> str:
    options = secrets_store.mode_labels()
    if len(options) == 1:
        print()
        print("Your API key won't be saved: you'll enter it each time you run")
        print("this tool. (Saving it requires Windows Hello on Windows, or the")
        print("signed desktop app on macOS.)")
        return secrets_store.MODE_NONE

    current = cfg.get("key_storage") or secrets_store.MODE_PROTECTED
    default_index = next(
        (i for i, (mode, _) in enumerate(options, 1) if mode == current), 1
    )
    print()
    print("How should your API key be stored?")
    for i, (_, label) in enumerate(options, 1):
        print("  {}) {}".format(i, label))
    while True:
        raw = input("Choose [{}]: ".format(default_index)).strip()
        if not raw:
            return options[default_index - 1][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        print("Please enter a number from 1 to {}.".format(len(options)))


def run_configure_wizard():
    cfg = config_mod.load_config()

    print("=== FormSmarts PDF Downloader - Configuration ===")
    print()

    current_dir = cfg["download_directory"]
    new_dir = input("Download directory [{}]: ".format(current_dir)).strip()
    if new_dir:
        cfg["download_directory"] = new_dir
    Path(cfg["download_directory"]).mkdir(parents=True, exist_ok=True)

    print()
    print("FormSmarts credentials (Account Overview and Security Settings")
    print("in your FormSmarts account).")
    current_account = cfg.get("account_id") or ""
    account_id = input("Account ID (e.g. FSA-123456) [{}]: ".format(current_account)).strip()
    account_id = account_id or current_account
    if not account_id:
        print("Account ID is required. Configuration was not saved.")
        return
    if not config_mod.ACCOUNT_ID_RE.match(account_id):
        print(
            "'{}' doesn't look like a valid Account ID (expected format: "
            "FSA-123456). Configuration was not saved.".format(account_id)
        )
        return

    legacy_key = _migrate_legacy(cfg, quiet=True)
    if current_account and current_account != account_id:
        secrets_store.delete_api_key(current_account)
    cfg["account_id"] = account_id

    mode = _choose_storage(cfg)
    if mode == secrets_store.MODE_NONE:
        secrets_store.delete_api_key(account_id)
    else:
        keep_existing = account_id == current_account and (
            legacy_key or secrets_store.has_saved_key(account_id)
        )
        prompt = "API Key (input hidden{}): ".format(
            ", leave blank to keep the saved key" if keep_existing else ""
        )
        api_key = getpass.getpass(prompt).strip() or (legacy_key if keep_existing else "")
        if api_key:
            print("Verify with {} to save the key...".format(secrets_store.protection_name()))
            try:
                secrets_store.save_api_key(account_id, api_key)
                print("API key saved.")
            except secrets_store.KeyStoreError as e:
                print("The API key could not be saved: {}".format(e))
                print("You'll be asked for it each time you run this tool.")
                mode = secrets_store.MODE_NONE
        elif not keep_existing:
            print("No API key entered; you'll be asked for it when downloading.")
            mode = secrets_store.MODE_NONE

    cfg["key_storage"] = mode
    config_mod.save_config(cfg)
    print()
    print("Configuration saved to {}".format(config_mod.config_path()))


def _migrate_legacy(cfg: dict, quiet: bool = False):
    """Versions before 1.1 saved the key unprotected in the OS credential
    store. Remove it from there, re-saving it with OS protection if
    possible. Returns the legacy key, if there was one."""
    if "key_storage" in cfg or not cfg.get("account_id"):
        return None
    account_id = cfg["account_id"]
    key = secrets_store.take_legacy_key(account_id)
    mode = secrets_store.MODE_NONE
    if key and not quiet:
        print("Your saved API key was stored without protection by an earlier")
        print("version of this tool; it has been removed from there.")
        if secrets_store.protected_available():
            print("Verify with {} to save it securely...".format(
                secrets_store.protection_name()))
            try:
                secrets_store.save_api_key(account_id, key)
                mode = secrets_store.MODE_PROTECTED
                print("API key saved.")
            except secrets_store.KeyStoreError as e:
                print("It could not be saved securely ({}).".format(e))
        if mode == secrets_store.MODE_NONE:
            print("You'll be asked for it each time (run --configure to change this).")
        print()
    if not quiet:
        cfg["key_storage"] = mode
        config_mod.save_config(cfg)
    return key


def _resolve_api_key(cfg: dict) -> str:
    legacy = _migrate_legacy(cfg)
    if legacy:
        return legacy

    account_id = cfg.get("account_id")
    if secrets_store.effective_mode(cfg) == secrets_store.MODE_PROTECTED:
        print("Verify with {} to unlock your API key...".format(
            secrets_store.protection_name()))
        try:
            key = secrets_store.load_api_key(account_id)
            if key:
                return key
            print("No saved API key was found.")
        except secrets_store.KeyStoreError as e:
            print("Couldn't unlock the saved API key: {}".format(e))
    elif cfg.get("key_storage") == secrets_store.MODE_PROTECTED:
        print("Your API key is saved for the desktop app, which this command")
        print("line tool can't access on this computer.")

    return getpass.getpass("API Key (input hidden, not saved): ").strip()


def cmd_download(args):
    try:
        # Imported lazily so --configure works without formsmarts installed.
        from . import downloader
    except ImportError as e:
        raise SystemExit(str(e)) from e

    cfg = config_mod.load_config()
    if not cfg.get("account_id"):
        print("It looks like this is your first time running this tool.")
        print("Let's set up your download folder and FormSmarts account first.")
        print()
        run_configure_wizard()
        print()
        cfg = config_mod.load_config()
        if not cfg.get("account_id"):
            print("Setup wasn't completed, so there's nothing to download yet.")
            print("Run the tool again to try setup once more.")
            sys.exit(1)

    form_id = args.form_id or input("Form ID: ").strip()
    if not form_id:
        print("A Form ID is required.")
        sys.exit(1)

    start_date = (
        _parse_date_arg(args.start_date)
        if args.start_date
        else _prompt_date("Start date (YYYY-MM-DD)")
    )
    end_date = (
        _parse_date_arg(args.end_date)
        if args.end_date
        else _prompt_date("End date (YYYY-MM-DD)", default=date.today())
    )
    if end_date < start_date:
        print("End date cannot be before the start date.")
        sys.exit(1)

    api_key = _resolve_api_key(cfg)
    if not api_key:
        print("An API key is required. Run with --configure to set one.")
        sys.exit(1)

    output_dir = downloader.build_output_dir(
        cfg["download_directory"], form_id, start_date, end_date
    )
    print("Saving PDFs to: {}".format(output_dir))
    print()

    # Counts are tracked here (not just via the return value) so a summary
    # can always be printed, even if the run is cut short by an error.
    counts = {"downloaded": 0, "skipped": 0, "failed": []}

    def progress(status, ref, extra):
        if status == "ok":
            counts["downloaded"] += 1
            print("  downloaded {} -> {}".format(ref, extra.name))
        elif status == "skip":
            counts["skipped"] += 1
            print("  already downloaded, skipping {}".format(ref))
        elif status == "error":
            counts["failed"].append((ref, extra))
            print("  FAILED {}: {}".format(ref, extra))

    error_message = None
    try:
        downloader.download_submissions(
            cfg["account_id"],
            api_key,
            form_id,
            start_date,
            end_date,
            output_dir,
            progress_cb=progress,
        )
    except downloader.AuthenticationError:
        error_message = "Authentication failed. Check the Account ID and API key (run --configure)."
    except (downloader.APIRequestError, downloader.APIError) as e:
        error_message = "FormSmarts API error: {}".format(e)
    except Exception as e:
        # Covers anything not modeled by formsmarts' own exceptions, e.g. no
        # internet connection, DNS failure, or a request timeout.
        error_message = "Couldn't reach FormSmarts: {}".format(e)

    print()
    if error_message:
        print(error_message)
    print(
        "Done. Downloaded {}, skipped {} (already present), failed {}.".format(
            counts["downloaded"], counts["skipped"], len(counts["failed"])
        )
    )
    if counts["failed"]:
        print("Failed submissions:")
        for ref, err in counts["failed"]:
            print("  {}: {}".format(ref, err))
    if error_message or counts["failed"]:
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fs-pdf-downloader",
        description="Download FormSmarts submission PDFs between two dates.",
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Run the configuration wizard (download folder, account, API key).",
    )
    parser.add_argument(
        "--forget-key",
        action="store_true",
        help="Delete the saved API key from this computer.",
    )
    parser.add_argument("--form-id", help="FormSmarts form ID.")
    parser.add_argument("--start-date", help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="End date, YYYY-MM-DD (default: today).")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.configure:
        run_configure_wizard()
        return
    if args.forget_key:
        cfg = config_mod.load_config()
        secrets_store.forget_everything(cfg.get("account_id"))
        if cfg.get("account_id"):
            cfg["key_storage"] = secrets_store.MODE_NONE
            config_mod.save_config(cfg)
        print("Any saved API key has been removed from this computer.")
        return
    cmd_download(args)


if __name__ == "__main__":
    main()
