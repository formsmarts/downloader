"""Command-line interface: interactive PDF download + configuration wizard."""

import argparse
import getpass
import re
import sys
from datetime import date, datetime
from pathlib import Path

from . import config as config_mod
from . import secrets_store

_ACCOUNT_ID_RE = re.compile(r"^FSA-\d+$")


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
    if not _ACCOUNT_ID_RE.match(account_id):
        print(
            "'{}' doesn't look like a valid Account ID (expected format: "
            "FSA-123456). Configuration was not saved.".format(account_id)
        )
        return
    cfg["account_id"] = account_id

    api_key = getpass.getpass(
        "API Key (input hidden, leave blank to keep the existing key): "
    ).strip()

    if api_key:
        try:
            secrets_store.save_api_key(account_id, api_key)
            print("API key saved to the OS secure credential store.")
        except secrets_store.KeyringUnavailableError:
            print()
            print("WARNING: no secure OS credential store (Keychain / Credential")
            print("Locker / Secret Service) is available on this system.")
            print(
                "The API key will NOT be saved to disk; you will be prompted "
                "for it each time you run this tool."
            )

    config_mod.save_config(cfg)
    print()
    print("Configuration saved to {}".format(config_mod.config_path()))


def _resolve_api_key(cfg: dict) -> str:
    account_id = cfg.get("account_id")

    try:
        key = secrets_store.get_api_key(account_id)
        if key:
            return key
    except secrets_store.KeyringUnavailableError:
        pass

    return getpass.getpass(
        "API Key (not saved, needed for this run only): "
    ).strip()


def cmd_download(args):
    from . import downloader  # imported lazily so --configure works without formsmarts installed

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
        help="Run the configuration wizard (download folder + API key).",
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
    cmd_download(args)


if __name__ == "__main__":
    main()
