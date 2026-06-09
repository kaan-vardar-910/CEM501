"""Local web dashboard for testing the CEM501 agent (BONUS — test interface).

A dependency-free HTTP server built on Python's standard library that exposes
the agent's capabilities as small JSON endpoints and serves a single-page
dashboard. It is intended purely as a local testing/demo surface: it binds to
127.0.0.1 only, defaults every send to dry-run, and reuses the exact same
triage, drafting, memory and guardrail code as the CLI agent.

Run:  python project/webapp.py   then open http://127.0.0.1:8000
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from reader import (
    fetch_recent_emails,
    get_triage_config,
    get_default_triage_config,
    save_triage_config,
    reload_contacts_cache,
)
from contacts import load_contacts, save_contacts
from digest import build_digest_data, render_digest_text
from templates import (
    draft_email_reply,
    draft_rfi,
    draft_submittal_transmittal,
    draft_delay_notice,
    extract_contract_fields,
    summarize_email,
)
from daily_report_store import _extract_text as extract_file_text
from memory import load_memory, get_stats_summary
from telegram_notifier import send_telegram_alert
from agent import send_email_web
from profiles import (
    load_profiles,
    save_profiles,
    get_active_signature,
    get_active_profile,
)
from document_formatter import (
    save_as_docx,
    save_as_pdf,
    save_as_both,
    get_output_path,
)
from document_sender import (
    send_document,
    build_default_subject,
    build_default_body,
)
from daily_report_store import (
    create_report,
    load_report,
    save_report,
    list_reports,
    upload_source_file,
    remove_source_file,
    mark_finalized,
    delete_report,
    get_report_folder,
    find_today_draft,
)
from daily_report_generator import (
    extract_fields_from_sources,
    generate_report_text,
)
from weather import get_site_weather, get_weather
from cities import list_cities
from daily_report_excel import build_daily_report_excel

HOST = "127.0.0.1"
PORT = 8000
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
CONTRACTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "contracts"
)


def _configured(value: str | None) -> bool:
    """True only if an env var holds a real (non-placeholder) value.

    The .env.example ships placeholder strings like ``your_key_here``; treating
    those as configured would make the status chips lie, so they are filtered.
    """
    if not value:
        return False
    placeholder = value.strip().lower()
    return not (
        placeholder.startswith("your_")
        or placeholder in ("your-key-here", "sk-ant-your-key-here", "")
        or "your-" in placeholder
    )


def _api_status() -> dict:
    """Report which credentials/features are configured (no secrets leaked)."""
    return {
        "anthropic": _configured(os.getenv("ANTHROPIC_API_KEY")),
        "email": _configured(os.getenv("EMAIL_ADDRESS")),
        "smtp": _configured(
            os.getenv("APP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
        ),
        "telegram": _configured(os.getenv("TELEGRAM_BOT_TOKEN"))
        and _configured(os.getenv("TELEGRAM_CHAT_ID")),
    }


def _api_inbox(use_test: bool) -> dict:
    """Fetch and triage emails for the inbox view."""
    emails = fetch_recent_emails(use_test_data=use_test)
    return {"emails": emails, "count": len(emails)}


def _api_digest(emails: list[dict]) -> dict:
    """Generate the digest for a provided list of triaged emails.

    Returns both the structured data (for the rich HTML view) and the plain-text
    rendering (for copy/paste, Telegram and logs). Summaries are computed once.
    """
    if not emails:
        emails = fetch_recent_emails(use_test_data=True)
    data = build_digest_data(emails)
    return {"data": data, "digest": render_digest_text(data)}


def _split_addresses(value) -> list[str]:
    """Accept a list or comma-separated string and return a clean list."""
    if isinstance(value, list):
        items = value
    else:
        items = str(value or "").split(",")
    return [item.strip() for item in items if str(item).strip()]


def _doc_settings(data: dict) -> dict:
    """Build the formatter/sender ``settings`` dict from the active profile.

    Profile fields supply the contractor identity and signature; the document
    form supplies the per-document project name and contract number.
    """
    profile = get_active_profile() or {}
    full_name = " ".join(
        part
        for part in (profile.get("first_name"), profile.get("last_name"))
        if part
    ).strip()
    return {
        "project_name": data.get("project_name", ""),
        "contractor_name": profile.get("company", ""),
        "contract_number": data.get("contract_number", ""),
        "prepared_by": full_name,
        "title": profile.get("title", ""),
        "signature_block": get_active_signature(),
    }


def _api_doc_save(data: dict) -> dict:
    """Save the generated document text to outputs/ in the chosen format(s)."""
    text = data.get("text", "")
    doc_type = data.get("doc_type", "Document")
    fmt = (data.get("format", "both") or "both").lower()
    settings = _doc_settings(data)
    if not text.strip():
        return {"error": "Nothing to save — generate the document first."}

    if fmt == "docx":
        path = save_as_docx(
            text, doc_type, get_output_path(doc_type, "docx"), settings
        )
        return {"files": {"docx": path}}
    if fmt == "pdf":
        path = save_as_pdf(
            text, doc_type, get_output_path(doc_type, "pdf"), settings
        )
        return {"files": {"pdf": path}}
    base = get_output_path(doc_type, "docx")
    return {"files": save_as_both(text, doc_type, base, settings)}


def _api_doc_draft_body(data: dict) -> dict:
    """Return a default subject and an LLM-drafted cover-email body."""
    settings = _doc_settings(data)
    doc_type = data.get("doc_type", "Document")
    return {
        "subject": build_default_subject(doc_type, settings),
        "body": build_default_body(doc_type, settings),
    }


def _api_doc_send(data: dict) -> dict:
    """Save the document (if needed) then send it with attachments."""
    text = data.get("text", "")
    doc_type = data.get("doc_type", "Document")
    if not text.strip():
        return {"sent": False, "message": "Generate the document first."}

    saved = _api_doc_save(data)
    if "error" in saved:
        return {"sent": False, "message": saved["error"]}
    files = saved.get("files", {})
    attachments = list(files.values())

    to_addresses = _split_addresses(data.get("to"))
    cc_addresses = _split_addresses(data.get("cc"))
    bcc_addresses = _split_addresses(data.get("bcc"))
    dry_run = bool(data.get("dry_run", True))

    sent = send_document(
        doc_type=doc_type,
        generated_text=text,
        attachment_paths=attachments,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        bcc_addresses=bcc_addresses,
        subject=data.get("subject", ""),
        body=data.get("body", ""),
        dry_run=dry_run,
    )
    recipients = len(to_addresses) + len(cc_addresses) + len(bcc_addresses)
    if sent and dry_run:
        message = f"[DRY RUN] Would send to {recipients} recipient(s)."
    elif sent:
        message = f"Sent successfully to {recipients} recipient(s)."
    else:
        message = "Not sent — see server console for guardrail details."
    return {"sent": sent, "dry_run": dry_run, "message": message, "files": files}


def _safe_contract_path(name: str) -> str | None:
    """Resolve ``name`` to a path inside CONTRACTS_DIR, or None if unsafe."""
    base = os.path.basename(str(name)).strip()
    if not base or base in (".", ".."):
        return None
    path = os.path.normpath(os.path.join(CONTRACTS_DIR, base))
    if os.path.dirname(path) != os.path.normpath(CONTRACTS_DIR):
        return None
    return path


def _api_contract_files() -> dict:
    """List uploaded contract files with size and modified time."""
    files: list[dict] = []
    if os.path.isdir(CONTRACTS_DIR):
        for name in sorted(os.listdir(CONTRACTS_DIR)):
            path = os.path.join(CONTRACTS_DIR, name)
            if os.path.isfile(path):
                stat = os.stat(path)
                files.append(
                    {
                        "name": name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime
                        ).strftime("%Y-%m-%d %H:%M"),
                    }
                )
    return {"files": files}


def _api_contract_upload(data: dict) -> dict:
    """Decode a base64 upload and store it in CONTRACTS_DIR."""
    path = _safe_contract_path(data.get("name", ""))
    if not path:
        return {"error": "Invalid file name."}
    try:
        content = base64.b64decode(data.get("content_b64", ""))
    except (ValueError, TypeError):
        return {"error": "Could not decode the uploaded file."}
    os.makedirs(CONTRACTS_DIR, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)
    return {"saved": True, "name": os.path.basename(path)}


def _api_contract_delete(data: dict) -> dict:
    """Delete a single contract file by name."""
    path = _safe_contract_path(data.get("name", ""))
    if not path:
        return {"error": "Invalid file name."}
    if os.path.isfile(path):
        os.remove(path)
        return {"deleted": True}
    return {"error": "File not found."}


_OUTPUT_TYPE_LABELS = {
    "RFI": "RFI",
    "SUBMITTALTRANSMITTAL": "Submittal",
    "SUBMITTAL": "Submittal",
    "DELAYNOTICE": "Delay Notice",
}


def _output_type(name: str) -> str:
    """Infer a human document type from an outputs/ file name prefix."""
    prefix = str(name).split("_", 1)[0].upper()
    return _OUTPUT_TYPE_LABELS.get(prefix, prefix.title() or "Document")


def _api_outputs() -> dict:
    """List generated documents saved in outputs/ (newest first)."""
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "outputs"
    )
    files: list[dict] = []
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            path = os.path.join(output_dir, name)
            if os.path.isfile(path):
                stat = os.stat(path)
                files.append(
                    {
                        "name": name,
                        "type": _output_type(name),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime
                        ).strftime("%Y-%m-%d %H:%M"),
                        "source": "output",
                        "download_url": "/api/output-file?name="
                        + quote(name),
                        "mtime": stat.st_mtime,
                    }
                )
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return {"files": files}


def _report_documents() -> list[dict]:
    """List exported daily-report files (docx/pdf/xlsx) across all reports."""
    docs: list[dict] = []
    for entry in list_reports():
        report_id = entry.get("id", "")
        if not report_id:
            continue
        folder = get_report_folder(report_id)
        number = entry.get("report_number", report_id)
        for fmt in ("docx", "pdf", "xlsx"):
            path = os.path.join(folder, f"{report_id}.{fmt}")
            if os.path.isfile(path):
                stat = os.stat(path)
                docs.append(
                    {
                        "name": f"{report_id}.{fmt}",
                        "type": "Daily Report",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime
                        ).strftime("%Y-%m-%d %H:%M"),
                        "source": "report",
                        "report_id": report_id,
                        "fmt": fmt,
                        "report_number": number,
                        "download_url": (
                            f"/api/report/file?id={quote(report_id)}&fmt={fmt}"
                        ),
                        "mtime": stat.st_mtime,
                    }
                )
    return docs


def _api_report_file_delete(data: dict) -> dict:
    """Delete a single exported daily-report file (docx/pdf/xlsx)."""
    report_id = os.path.basename(str(data.get("report_id", "")))
    fmt = str(data.get("fmt", "")).lower()
    if not report_id or fmt not in ("docx", "pdf", "xlsx"):
        return {"error": "Invalid report file."}
    path = os.path.join(get_report_folder(report_id), f"{report_id}.{fmt}")
    if os.path.isfile(path):
        os.remove(path)
        return {"deleted": True}
    return {"error": "File not found."}


def _api_output_delete(data: dict) -> dict:
    """Delete a saved document from outputs/ by file name."""
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "outputs"
    )
    base = os.path.basename(str(data.get("name", ""))).strip()
    path = os.path.normpath(os.path.join(output_dir, base))
    if not base or os.path.dirname(path) != os.path.normpath(output_dir):
        return {"error": "Invalid file name."}
    if os.path.isfile(path):
        os.remove(path)
        return {"deleted": True}
    return {"error": "File not found."}


def _api_contract_extract(data: dict) -> dict:
    """Read an uploaded contract file and extract delay-notice fields via LLM."""
    path = _safe_contract_path(data.get("name", ""))
    if not path:
        return {"error": "Invalid file name."}
    if not os.path.isfile(path):
        return {"error": "File not found."}
    text = extract_file_text(path)
    if not text.strip():
        return {"error": "Could not read text from this contract file."}
    fields = extract_contract_fields(text)
    return {"fields": fields}


def _report_defaults() -> dict:
    """Default project_name / prepared_by for a new report, from the profile."""
    profile = get_active_profile() or {}
    full_name = " ".join(
        part
        for part in (profile.get("first_name"), profile.get("last_name"))
        if part
    ).strip()
    return {
        "project_name": profile.get("project", ""),
        "prepared_by": full_name,
    }


def _report_doc_settings(report: dict) -> dict:
    """Build formatter/sender settings for a daily report from profile + report."""
    profile = get_active_profile() or {}
    return {
        "project_name": report.get("project_name", ""),
        "contractor_name": profile.get("company", ""),
        "contract_number": "",
        "prepared_by": report.get("prepared_by", ""),
        "title": profile.get("title", ""),
        "signature_block": get_active_signature(),
        "report_date": report.get("date", ""),
    }


def _api_weather() -> dict:
    """Fetch weather using the active profile's site location, falling back to
    the SITE_LAT/SITE_LNG env vars when the profile has no coordinates set."""
    profile = get_active_profile() or {}
    lat_raw = (profile.get("site_lat") or "").strip()
    lng_raw = (profile.get("site_lng") or "").strip()
    if lat_raw and lng_raw:
        try:
            result = get_weather(float(lat_raw), float(lng_raw))
            result["configured"] = True
            result["city"] = profile.get("site_city", "")
            return result
        except ValueError:
            pass
    return get_site_weather()


def _api_report_init(data: dict) -> dict:
    """Continue today's draft if one exists, else create a fresh report.

    ``force_new=True`` always creates a brand-new report (used by the explicit
    "+ New Report" button) instead of resuming today's draft.
    """
    date_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    if not data.get("force_new"):
        existing = find_today_draft(date_str)
        if existing:
            return {"report": existing, "resumed": True}
    report = create_report(date_str, _report_defaults())
    return {"report": report, "resumed": False}


def _api_report_save(data: dict) -> dict:
    """Persist edited report fields. Re-opens a finalized report if asked."""
    report = data.get("report") or {}
    if not report.get("id"):
        return {"error": "Missing report id."}
    if data.get("reopen") and report.get("status") == "finalized":
        report["status"] = "draft"
    save_report(report)
    return {"saved": True, "report": load_report(report["id"])}


def _api_report_upload(data: dict) -> dict:
    """Decode an uploaded source file and extract its text into the report."""
    report_id = data.get("id", "")
    name = os.path.basename(str(data.get("name", ""))).strip()
    if not report_id or not name:
        return {"error": "Missing report id or file name."}
    try:
        content = base64.b64decode(data.get("content_b64", ""))
    except (ValueError, TypeError):
        return {"error": "Could not decode the uploaded file."}

    tmp_dir = os.path.join(get_report_folder(report_id), "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, name)
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(content)
        info = upload_source_file(report_id, tmp_path)
    finally:
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
        if os.path.isdir(tmp_dir) and not os.listdir(tmp_dir):
            os.rmdir(tmp_dir)
    return {"uploaded": True, "info": info, "report": load_report(report_id)}


def _api_report_remove_source(data: dict) -> dict:
    """Remove one source file from a report."""
    report_id = data.get("id", "")
    filename = data.get("filename", "")
    if not report_id or not filename:
        return {"error": "Missing report id or file name."}
    remove_source_file(report_id, filename)
    return {"removed": True, "report": load_report(report_id)}


def _api_report_extract(data: dict) -> dict:
    """Run LLM field extraction over a report's source files."""
    report_id = data.get("id", "")
    if not report_id:
        return {"error": "Missing report id."}
    fields = extract_fields_from_sources(report_id)
    if not fields:
        return {"fields": {}, "message": "No data extracted from source files."}
    return {"fields": fields}


def _api_report_generate(data: dict) -> dict:
    """Generate the formatted report text from current field values."""
    report = data.get("report") or {}
    if not report.get("id"):
        return {"error": "Missing report data."}
    text = generate_report_text(report)
    return {"text": text}


def _report_export(report: dict, text: str, fmt: str) -> dict:
    """Save the report text as docx/pdf/both inside the report folder."""
    folder = get_report_folder(report["id"])
    os.makedirs(folder, exist_ok=True)
    settings = _report_doc_settings(report)
    doc_type = "Daily Report"
    docx_path = os.path.join(folder, f"{report['id']}.docx")
    pdf_path = os.path.join(folder, f"{report['id']}.pdf")
    xlsx_path = os.path.join(folder, f"{report['id']}.xlsx")
    if fmt == "xlsx":
        return {"xlsx": build_daily_report_excel(xlsx_path, report)}
    if fmt == "docx":
        return {"docx": save_as_docx(text, doc_type, docx_path, settings)}
    if fmt == "pdf":
        return {"pdf": save_as_pdf(text, doc_type, pdf_path, settings)}
    return save_as_both(text, doc_type, docx_path, settings)


def _api_report_save_files(data: dict) -> dict:
    """Export the generated report text to the report folder (docx/pdf/both)."""
    report = data.get("report") or {}
    text = data.get("text", "")
    fmt = (data.get("format", "both") or "both").lower()
    if not report.get("id"):
        return {"error": "Missing report data."}
    # The Excel template is built from structured data, so it does not require
    # the generated narrative text; other formats render that text.
    if fmt != "xlsx" and not text.strip():
        return {"error": "Generate the report before saving files."}
    files = _report_export(report, text, fmt)
    # Refresh index has_docx/has_pdf flags.
    save_report(load_report(report["id"]))
    return {"files": files}


def _api_report_send(data: dict) -> dict:
    """Export report files then email them with the existing guardrails."""
    report = data.get("report") or {}
    text = data.get("text", "")
    if not report.get("id"):
        return {"sent": False, "message": "Missing report data."}
    if not text.strip():
        return {"sent": False, "message": "Generate the report first."}

    fmt = (data.get("format", "both") or "both").lower()
    files = _report_export(report, text, fmt)
    save_report(load_report(report["id"]))
    attachments = list(files.values())

    to_addresses = _split_addresses(data.get("to"))
    cc_addresses = _split_addresses(data.get("cc"))
    bcc_addresses = _split_addresses(data.get("bcc"))
    dry_run = bool(data.get("dry_run", True))

    sent = send_document(
        doc_type="Daily Report",
        generated_text=text,
        attachment_paths=attachments,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        bcc_addresses=bcc_addresses,
        subject=data.get("subject", ""),
        body=data.get("body", ""),
        dry_run=dry_run,
    )
    recipients = len(to_addresses) + len(cc_addresses) + len(bcc_addresses)
    if sent and dry_run:
        message = f"[DRY RUN] Would send to {recipients} recipient(s)."
    elif sent:
        message = f"Sent successfully to {recipients} recipient(s)."
    else:
        message = "Not sent — see server console for guardrail details."
    return {"sent": sent, "dry_run": dry_run, "message": message, "files": files}


def _api_report_finalize(data: dict) -> dict:
    """Mark a report finalized."""
    report_id = data.get("id", "")
    if not report_id:
        return {"error": "Missing report id."}
    mark_finalized(report_id)
    return {"finalized": True, "report": load_report(report_id)}


def _api_report_delete(data: dict) -> dict:
    """Delete a report folder and its index entry."""
    report_id = data.get("id", "")
    if not report_id:
        return {"error": "Missing report id."}
    delete_report(report_id)
    return {"deleted": True}


def _api_report_subject_body(data: dict) -> dict:
    """Default subject/body for sending a daily report."""
    report = data.get("report") or {}
    subject = (
        f"{report.get('project_name', '')} \u2014 Daily Report "
        f"\u2014 {report.get('date', '')}"
    ).strip(" \u2014")
    settings = _report_doc_settings(report)
    body = build_default_body("Daily Report", settings)
    return {"subject": subject, "body": body}


TELEGRAM_SENT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "telegram_sent.json"
)


def _load_alerted() -> set[str]:
    """Load the set of email keys already pushed to Telegram."""
    try:
        with open(TELEGRAM_SENT_PATH, "r", encoding="utf-8") as handle:
            return set(json.load(handle))
    except (OSError, json.JSONDecodeError):
        return set()


def _save_alerted(keys: set[str]) -> None:
    """Persist the alerted-key set (capped to the most recent 500)."""
    try:
        with open(TELEGRAM_SENT_PATH, "w", encoding="utf-8") as handle:
            json.dump(list(keys)[-500:], handle)
    except OSError as error:
        print(f"[telegram] Could not save alert log: {error}")


def _email_key(email: dict) -> str:
    """Stable identity for an email (sender + subject + date)."""
    return "|".join(
        str(email.get(field, "")).strip()
        for field in ("sender", "subject", "date")
    )


def _api_telegram_urgent(data: dict) -> dict:
    """Push Telegram alerts for URGENT emails, skipping already-sent ones.

    ``force=True`` re-sends every current URGENT email; otherwise only emails
    not previously alerted are sent (deduplicated across refreshes/sessions).
    """
    emails = data.get("emails", []) or []
    force = bool(data.get("force", False))
    urgent = [e for e in emails if e.get("triage_category") == "URGENT"]
    if not urgent:
        return {"sent": 0, "skipped": 0, "total": 0, "message": "No URGENT emails."}

    alerted = _load_alerted()
    sent = skipped = 0
    for email in urgent:
        key = _email_key(email)
        if not force and key in alerted:
            skipped += 1
            continue
        ok = send_telegram_alert(
            subject=email.get("subject", ""),
            sender=email.get("sender", ""),
            preview=email.get("summary") or email.get("preview", ""),
        )
        if ok:
            sent += 1
            alerted.add(key)
        else:
            skipped += 1
    _save_alerted(alerted)
    message = f"Sent {sent}, skipped {skipped} of {len(urgent)} URGENT."
    return {"sent": sent, "skipped": skipped, "total": len(urgent), "message": message}


def _api_memory() -> dict:
    """Return memory stats, known sender profiles and saved documents."""
    memory = load_memory()
    documents = _api_outputs().get("files", []) + _report_documents()
    documents.sort(key=lambda f: f.get("mtime", 0), reverse=True)
    for f in documents:
        f.pop("mtime", None)
    return {
        "summary": get_stats_summary(memory),
        "profiles": len(memory.get("sender_profiles", {})),
        "sent_history": len(memory.get("sent_history", [])),
        "documents": documents,
    }


class Handler(BaseHTTPRequestHandler):
    """Routes static files (GET) and JSON API calls (GET/POST)."""

    def log_message(self, *args) -> None:  # noqa: D401 - quiet default logging.
        """Suppress the noisy default per-request logging."""
        return

    # --- helpers ---------------------------------------------------------
    def _send_json(self, payload: dict, status: int = 200) -> None:
        """Serialize ``payload`` to JSON and write it with the right headers."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        """Read and parse a JSON request body, returning {} on any problem."""
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _serve_static(self, path: str) -> None:
        """Serve index.html (or favicon) from the web directory."""
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        file_path = os.path.normpath(os.path.join(WEB_DIR, rel))
        # Prevent path traversal outside the web directory.
        if not file_path.startswith(WEB_DIR):
            self.send_error(403, "Forbidden")
            return
        if not os.path.isfile(file_path):
            self.send_error(404, "Not found")
            return
        content_type = "text/html; charset=utf-8"
        if file_path.endswith(".css"):
            content_type = "text/css"
        elif file_path.endswith(".js"):
            content_type = "application/javascript"
        with open(file_path, "rb") as handle:
            data = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # Never cache the dashboard so edits show up on a normal refresh.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_report_file(self, report_id: str, fmt: str) -> None:
        """Stream a saved daily-report .docx/.pdf/.xlsx as a browser download."""
        fmt = str(fmt).lower()
        if fmt not in ("pdf", "docx", "xlsx"):
            fmt = "docx"
        safe_id = os.path.basename(str(report_id))
        path = os.path.join(get_report_folder(safe_id), f"{safe_id}.{fmt}")
        if not safe_id or not os.path.isfile(path):
            self.send_error(404, "File not found")
            return
        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
        }
        content_type = content_types[fmt]
        with open(path, "rb") as handle:
            data = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{safe_id}.{fmt}"',
        )
        self.end_headers()
        self.wfile.write(data)

    def _serve_output_file(self, name: str) -> None:
        """Stream a saved document from outputs/ as a browser download."""
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "outputs"
        )
        base = os.path.basename(str(name)).strip()
        path = os.path.normpath(os.path.join(output_dir, base))
        if (
            not base
            or os.path.dirname(path) != os.path.normpath(output_dir)
            or not os.path.isfile(path)
        ):
            self.send_error(404, "File not found")
            return
        ext = os.path.splitext(base)[1].lower()
        content_types = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
        }
        content_type = content_types.get(ext, "application/octet-stream")
        with open(path, "rb") as handle:
            data = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Content-Disposition", f'attachment; filename="{base}"'
        )
        self.end_headers()
        self.wfile.write(data)

    # --- routing ---------------------------------------------------------
    def do_GET(self) -> None:
        """Handle GET: static files and read-only API endpoints."""
        parsed = urlparse(self.path)
        route = parsed.path
        try:
            if route == "/api/status":
                self._send_json(_api_status())
            elif route == "/api/inbox":
                params = parse_qs(parsed.query)
                use_test = params.get("test", ["true"])[0] != "false"
                self._send_json(_api_inbox(use_test))
            elif route == "/api/memory":
                self._send_json(_api_memory())
            elif route == "/api/triage-config":
                self._send_json(
                    {
                        "config": get_triage_config(),
                        "defaults": get_default_triage_config(),
                    }
                )
            elif route == "/api/profiles":
                self._send_json(load_profiles())
            elif route == "/api/contacts":
                self._send_json(load_contacts())
            elif route == "/api/contract-files":
                self._send_json(_api_contract_files())
            elif route == "/api/outputs":
                self._send_json(_api_outputs())
            elif route == "/api/output-file":
                params = parse_qs(parsed.query)
                self._serve_output_file(params.get("name", [""])[0])
            elif route == "/api/reports":
                self._send_json({"reports": list_reports()})
            elif route == "/api/report":
                params = parse_qs(parsed.query)
                report_id = params.get("id", [""])[0]
                self._send_json({"report": load_report(report_id)})
            elif route == "/api/weather":
                self._send_json(_api_weather())
            elif route == "/api/cities":
                self._send_json({"cities": list_cities()})
            elif route == "/api/report/file":
                params = parse_qs(parsed.query)
                self._serve_report_file(
                    params.get("id", [""])[0], params.get("fmt", ["docx"])[0]
                )
            elif route.startswith("/api/"):
                self._send_json({"error": "Unknown endpoint"}, status=404)
            else:
                self._serve_static(route)
        except Exception as error:  # noqa: BLE001 - report errors as JSON.
            self._send_json({"error": str(error)}, status=500)

    def do_POST(self) -> None:
        """Handle POST: digest, drafting, send and Telegram endpoints."""
        route = urlparse(self.path).path
        data = self._read_json_body()
        try:
            signature = get_active_signature()
            if route == "/api/digest":
                self._send_json(_api_digest(data.get("emails", [])))
            elif route == "/api/draft-reply":
                draft = draft_email_reply(
                    original_subject=data.get("subject", ""),
                    original_body=data.get("body", ""),
                    reply_intent=data.get("intent", "Acknowledge and respond."),
                    project_context=data.get(
                        "context", "CEM commercial construction project"
                    ),
                    signature=signature,
                )
                self._send_json({"draft": draft})
            elif route == "/api/rfi":
                doc = draft_rfi(
                    project_name=data.get("project_name", ""),
                    drawing_ref=data.get("drawing_ref", ""),
                    spec_ref=data.get("spec_ref", ""),
                    issue=data.get("issue", ""),
                    suggested_resolution=data.get("suggested_resolution", ""),
                    affected_trade=data.get("affected_trade", ""),
                    activity_start_date=data.get("activity_start_date", ""),
                    response_deadline=data.get("response_deadline", ""),
                    signature=signature,
                )
                self._send_json({"document": doc})
            elif route == "/api/submittal":
                doc = draft_submittal_transmittal(
                    project_name=data.get("project_name", ""),
                    submittal_no=data.get("submittal_no", ""),
                    revision=data.get("revision", ""),
                    spec_section=data.get("spec_section", ""),
                    description=data.get("description", ""),
                    supplier=data.get("supplier", ""),
                    copies=data.get("copies", ""),
                    certs=data.get("certs", ""),
                    action=data.get("action", ""),
                    notes=data.get("notes", ""),
                    signature=signature,
                )
                self._send_json({"document": doc})
            elif route == "/api/delay":
                activities = data.get("affected_activities", [])
                if isinstance(activities, str):
                    activities = [a.strip() for a in activities.split(",")]
                doc = draft_delay_notice(
                    project_name=data.get("project_name", ""),
                    contract_no=data.get("contract_no", ""),
                    contract_section=data.get("contract_section", ""),
                    start_date=data.get("start_date", ""),
                    end_date=data.get("end_date", ""),
                    affected_activities=activities,
                    days_requested=int(data.get("days_requested", 0) or 0),
                    supporting_data=data.get("supporting_data", ""),
                    signature=signature,
                )
                self._send_json({"document": doc})
            elif route == "/api/send":
                result = send_email_web(
                    to=data.get("to", ""),
                    subject=data.get("subject", ""),
                    body=data.get("body", ""),
                    dry_run=bool(data.get("dry_run", True)),
                    attachments=data.get("attachments", []),
                )
                self._send_json(result)
            elif route == "/api/triage-config":
                # Persist the edited keyword sets and apply them live.
                active = save_triage_config(
                    {
                        "urgent": data.get("urgent", []),
                        "action": data.get("action", []),
                        "fyi": data.get("fyi", []),
                        "vip": data.get("vip", []),
                    }
                )
                self._send_json({"saved": True, "config": active})
            elif route == "/api/profiles":
                saved = save_profiles(
                    {
                        "active": data.get("active", 0),
                        "profiles": data.get("profiles", []),
                    }
                )
                self._send_json({"saved": True, **saved})
            elif route == "/api/contacts":
                saved = save_contacts({"contacts": data.get("contacts", [])})
                # Refresh the reader's importance cache so triage updates live.
                reload_contacts_cache()
                self._send_json({"saved": True, **saved})
            elif route == "/api/summarize":
                summary = summarize_email(
                    data.get("body", ""),
                    sentences=int(data.get("sentences", 2) or 2),
                )
                self._send_json({"summary": summary})
            elif route == "/api/doc/save":
                self._send_json(_api_doc_save(data))
            elif route == "/api/doc/draft-body":
                self._send_json(_api_doc_draft_body(data))
            elif route == "/api/doc/send":
                self._send_json(_api_doc_send(data))
            elif route == "/api/contract-files":
                self._send_json(_api_contract_upload(data))
            elif route == "/api/contract-files/delete":
                self._send_json(_api_contract_delete(data))
            elif route == "/api/output-files/delete":
                self._send_json(_api_output_delete(data))
            elif route == "/api/report-file/delete":
                self._send_json(_api_report_file_delete(data))
            elif route == "/api/contract-files/extract":
                self._send_json(_api_contract_extract(data))
            elif route == "/api/report/init":
                self._send_json(_api_report_init(data))
            elif route == "/api/report/save":
                self._send_json(_api_report_save(data))
            elif route == "/api/report/upload":
                self._send_json(_api_report_upload(data))
            elif route == "/api/report/remove-source":
                self._send_json(_api_report_remove_source(data))
            elif route == "/api/report/extract":
                self._send_json(_api_report_extract(data))
            elif route == "/api/report/generate":
                self._send_json(_api_report_generate(data))
            elif route == "/api/report/save-files":
                self._send_json(_api_report_save_files(data))
            elif route == "/api/report/subject-body":
                self._send_json(_api_report_subject_body(data))
            elif route == "/api/report/send":
                self._send_json(_api_report_send(data))
            elif route == "/api/report/finalize":
                self._send_json(_api_report_finalize(data))
            elif route == "/api/report/delete":
                self._send_json(_api_report_delete(data))
            elif route == "/api/telegram-urgent":
                self._send_json(_api_telegram_urgent(data))
            elif route == "/api/telegram":
                ok = send_telegram_alert(
                    subject=data.get("subject", ""),
                    sender=data.get("sender", ""),
                    preview=data.get("preview", ""),
                )
                self._send_json({"sent": ok})
            else:
                self._send_json({"error": "Unknown endpoint"}, status=404)
        except Exception as error:  # noqa: BLE001 - report errors as JSON.
            self._send_json({"error": str(error)}, status=500)


def main() -> None:
    """Start the threaded dev server on localhost."""
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"CEM501 dashboard running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
