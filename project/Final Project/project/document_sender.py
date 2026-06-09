"""Send generated CEM documents by email, reusing the agent's send guardrails.

Wraps the existing send infrastructure in ``agent.py`` (recipient validation,
content checks, rate limiting and the ``sent_log.txt`` audit trail) and adds
document-specific behaviour: multipart messages with .docx / .pdf attachments,
sensible default subjects, and an LLM-drafted cover email body.

The web "Send" click is treated as the mandatory human confirmation, so this
module runs the remaining guardrails programmatically rather than prompting.
"""

from __future__ import annotations

import os
import smtplib
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from agent import (
    MAX_SENDS,
    RATE_WINDOW_SECONDS,
    _SEND_TIMESTAMPS,
    _append_sent_log,
    _within_rate_limit,
    check_content,
    validate_recipient,
)
from templates import _call_claude


def _clean_list(addresses: list[str] | None) -> list[str]:
    """Trim, drop blanks and de-duplicate a list of addresses."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in addresses or []:
        addr = str(raw).strip()
        if addr and addr.lower() not in seen:
            cleaned.append(addr)
            seen.add(addr.lower())
    return cleaned


def _print_preview(
    doc_type: str,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    attachment_paths: list[str],
) -> None:
    """Print the document send preview box to the server console."""
    names = ", ".join(os.path.basename(p) for p in attachment_paths) or "None"
    print("+---------------------------------------------+")
    print("| DOCUMENT SEND PREVIEW                        |")
    print(f"| Document: {doc_type}")
    print(f"| To: {', '.join(to_addresses)}")
    print(f"| CC: {', '.join(cc_addresses) or 'None'}")
    print(f"| Subject: {subject}")
    print(f"| Attachments: {names}")
    print("+---------------------------------------------+")


def _build_message(
    sender: str,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    body: str,
    attachment_paths: list[str],
) -> MIMEMultipart:
    """Assemble a multipart email with plain-text body and file attachments."""
    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = ", ".join(to_addresses)
    if cc_addresses:
        message["Cc"] = ", ".join(cc_addresses)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", _charset="utf-8"))

    for path in attachment_paths:
        if not path or not os.path.isfile(path):
            print(f"[doc-send] Skipping missing attachment: {path}")
            continue
        with open(path, "rb") as handle:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(handle.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(path)}"',
        )
        message.attach(part)
    return message


def send_document(
    doc_type: str,
    generated_text: str,
    attachment_paths: list[str],
    to_addresses: list[str],
    cc_addresses: list[str],
    bcc_addresses: list[str],
    subject: str,
    body: str,
    dry_run: bool = False,
) -> bool:
    """Send a document email through the agent's guardrails. Return success.

    ``generated_text`` is accepted for parity/logging; the actual content travels
    as attachments plus the ``body`` cover note. Returns True only when the email
    is sent (or, in dry-run mode, would have been sent).
    """
    to_addresses = _clean_list(to_addresses)
    cc_addresses = _clean_list(cc_addresses)
    bcc_addresses = _clean_list(bcc_addresses)

    _print_preview(doc_type, to_addresses, cc_addresses, subject, attachment_paths)

    if not to_addresses:
        print("[doc-send] No recipients; aborting.")
        return False

    # Guardrail 2 — recipient validation across To + CC + BCC.
    all_recipients = to_addresses + cc_addresses + bcc_addresses
    blocked, warnings = validate_recipient(", ".join(all_recipients))
    for warning in warnings:
        print(f"[doc-send][WARN] {warning}")
    if blocked:
        print("[doc-send] Blocked by recipient guardrail; not sent.")
        return False

    # Guardrail 3 — content checks (warn only; the Send click is confirmation).
    for warning in check_content(subject, body):
        print(f"[doc-send][WARN] {warning}")

    # Guardrail 4 — rate limiting.
    if not _within_rate_limit():
        print(
            f"[doc-send] Rate limit reached "
            f"({MAX_SENDS}/{RATE_WINDOW_SECONDS // 60} min); not sent."
        )
        return False

    if dry_run:
        print(f"[DRY RUN] Would send '{doc_type}' to: {', '.join(to_addresses)}")
        return True

    address = os.getenv("EMAIL_ADDRESS")
    app_password = os.getenv("APP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    if not address or not app_password:
        print("[doc-send] EMAIL_ADDRESS / APP_PASSWORD not set; cannot send.")
        return False

    message = _build_message(
        address, to_addresses, cc_addresses, subject, body, attachment_paths
    )
    envelope = to_addresses + cc_addresses + bcc_addresses
    try:
        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls()
            server.login(address, app_password)
            server.sendmail(address, envelope, message.as_string())
    except smtplib.SMTPAuthenticationError as error:
        print(f"[doc-send] SMTP authentication failed: {error}")
        return False
    except (smtplib.SMTPException, OSError) as error:
        print(f"[doc-send] SMTP error: {error}")
        return False

    _SEND_TIMESTAMPS.append(time.time())
    _append_sent_log(", ".join(envelope), subject, f"[{doc_type}] {body}")
    print(f"[doc-send] Document sent to {len(envelope)} recipient(s).")
    return True


def build_default_subject(doc_type: str, settings: dict) -> str:
    """Return ``[project] — [doc_type] — [today]`` as a default subject."""
    today = datetime.now().strftime("%Y-%m-%d")
    project = settings.get("project_name", "").strip() or "Project"
    return f"{project} — {doc_type} — {today}"


def build_default_body(doc_type: str, settings: dict) -> str:
    """Draft a short cover-email body via Claude, with a plain fallback."""
    project = settings.get("project_name", "the project")
    contractor = settings.get("contractor_name", "the contractor")
    signature = settings.get("signature_block", "")

    system_prompt = (
        "You are a professional project manager. Write a short (3-4 sentences) "
        "email body to accompany a "
        f"{doc_type} document. Use a front-loaded structure and a professional "
        "tone. Do not repeat the document content — just introduce it and state "
        "the action required. Output only the email body, no subject line."
    )
    user_prompt = (
        f"Write the email body for: {doc_type} from {contractor} to the "
        f"recipient. Project: {project}."
    )
    result = _call_claude(system_prompt, user_prompt)
    if result and not result.startswith("[ERROR]"):
        if signature and signature not in result:
            result = f"{result}\n\n{signature}"
        return result

    fallback = (
        f"Please find attached the {doc_type} for {project}. "
        "Kindly review and respond at your earliest convenience."
    )
    if signature:
        fallback = f"{fallback}\n\n{signature}"
    return fallback


if __name__ == "__main__":
    demo_settings = {
        "project_name": "Metro Station A",
        "contractor_name": "Meridian Construction Co.",
        "signature_block": "Jordan Rivera\nProject Manager",
    }
    print("Default subject:")
    print(" ", build_default_subject("RFI", demo_settings))
    print("\nDefault body (uses Claude if configured, else fallback):")
    print(build_default_body("RFI", demo_settings))
    print("\n--- Dry-run send test ---")
    send_document(
        doc_type="RFI",
        generated_text="Sample RFI text",
        attachment_paths=[],
        to_addresses=["architect@example.com"],
        cc_addresses=[],
        bcc_addresses=[],
        subject=build_default_subject("RFI", demo_settings),
        body="Please find attached the RFI for Metro Station A.",
        dry_run=True,
    )
