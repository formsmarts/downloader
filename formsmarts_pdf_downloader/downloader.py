"""Core download logic built on the FormSmarts API client."""

import re
import time
from datetime import date
from pathlib import Path

try:
    from formsmarts import (
        APIAuthenticator,
        FormEntry,
        APIError,
        APIRequestError,
        AuthenticationError,
    )
except ImportError as e:
    raise ImportError(
        "Missing dependency 'formsmarts'.\n"
        "Install requirements with:\n"
        "  pip install -r requirements.txt\n"
        "or run windows\\install.bat to set up everything automatically."
    ) from e

# Minimum delay between PDF download requests, so we don't hammer the API.
THROTTLE_SECONDS = 0.1

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9_-]+")


def _sanitize(value: str) -> str:
    return _SAFE_CHARS.sub("_", str(value).strip()) or "form"


def build_output_dir(base_dir, form_id: str, start_date: date, end_date: date) -> Path:
    folder_name = "{}_{}_to_{}".format(
        _sanitize(form_id), start_date.isoformat(), end_date.isoformat()
    )
    out_dir = Path(base_dir) / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def download_submissions(
    account_id: str,
    api_key: str,
    form_id: str,
    start_date: date,
    end_date: date,
    output_dir: Path,
    progress_cb=None,
    cancel_event=None,
):
    """Download every PDF for `form_id` submitted between start_date and
    end_date (inclusive) into output_dir. Returns (downloaded, skipped, failed).

    If `cancel_event` (a threading.Event) is given and gets set, the run stops
    before the next submission.
    """
    auth = APIAuthenticator(account_id, api_key)

    downloaded = 0
    skipped = 0
    failed = []

    entries = FormEntry.search_by_dates(
        auth, form_id=form_id, start_date=start_date, end_date=end_date
    )

    for entry in entries:
        if cancel_event is not None and cancel_event.is_set():
            break

        submitted_at = entry.submitted_at
        if submitted_at and not (start_date <= submitted_at.date() <= end_date):
            # Defensive: skip anything outside the requested range even if
            # the API's date filtering is looser than expected.
            continue

        ref = entry.reference_number
        if submitted_at:
            filename = "{}_{}.pdf".format(submitted_at.strftime("%Y%m%d_%H%M%S"), ref)
        else:
            filename = "{}.pdf".format(ref)
        dest = output_dir / filename

        if dest.exists():
            skipped += 1
            if progress_cb:
                progress_cb("skip", ref, dest)
            continue

        try:
            FormEntry.download_pdf(auth, ref_num=ref, io_stream=str(dest))
            downloaded += 1
            if progress_cb:
                progress_cb("ok", ref, dest)
        except AuthenticationError:
            raise
        except (APIRequestError, APIError) as e:
            failed.append((ref, str(e)))
            if progress_cb:
                progress_cb("error", ref, str(e))

        time.sleep(THROTTLE_SECONDS)

    return downloaded, skipped, failed
