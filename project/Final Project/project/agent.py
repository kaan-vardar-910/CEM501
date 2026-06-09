"""Full pipeline orchestrator (Milestone M4).

Ties every component together: load memory, fetch and triage email, print the
morning digest, fire Telegram alerts for urgent items, then walk the operator
through draft-and-confirm for each urgent/action email. The send path is
wrapped in four mandatory guardrails — confirmation, recipient validation,
content checks and rate limiting — because the send button is the most
dangerous button in any communication agent.
"""

from __future__ import annotations

import argparse
import os
import smtplib
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    BLUE = Fore.BLUE
    RESET = Style.RESET_ALL
    GRAY = Fore.WHITE
    GREEN = Fore.GREEN
except ImportError:
    RED = YELLOW = BLUE = RESET = GRAY = GREEN = ""

from reader import fetch_recent_emails
from digest import generate_digest
from templates import draft_email_reply
from memory import (
    load_memory,
    save_memory,
    update_sender_profile,
)
from telegram_notifier import send_telegram_alert

# Recipients we recognise; anyone else triggers a recipient-validation warning.
KNOWN_CONTACTS = [
    "inspector@example.com",
    "architect@example.com",
    "owner@example.com",
    "eor@example.com",
    "scheduler@example.com",
]
# Common typo'd mail domains worth a hard red warning before sending.
DOMAIN_TYPOS = ["gmial", "yhaoo", "outlok"]
# Placeholder tokens that should never survive into a real outgoing email.
PLACEHOLDER_TOKENS = ["[INSERT]", "[TODO]", "[PLACEHOLDER]", "[YOUR NAME]"]

# Rate-limit window: at most MAX_SENDS in any RATE_WINDOW_SECONDS span.
MAX_SENDS = 10
RATE_WINDOW_SECONDS = 600
_SEND_TIMESTAMPS: list[float] = []

SENT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "sent_log.txt"
)


def print_header() -> None:
    """Print the boxed startup banner with the current timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("╔══════════════════════════════════════════════════╗")
    print("║      CEM501 AI Communication Agent v1.0          ║")
    print(f"║      {timestamp:<44}║")
    print("╚══════════════════════════════════════════════════╝")


def _within_rate_limit() -> bool:
    """Return True if another send is allowed under the rolling window.

    Prunes timestamps older than the window, then checks the remaining count.
    Does not record the new send; the caller records it only on success.
    """
    now = time.time()
    cutoff = now - RATE_WINDOW_SECONDS
    _SEND_TIMESTAMPS[:] = [ts for ts in _SEND_TIMESTAMPS if ts > cutoff]
    return len(_SEND_TIMESTAMPS) < MAX_SENDS


def _confirm(prompt: str) -> str:
    """Read a single confirmation keystroke, lowered and stripped.

    Wrapped so a non-interactive environment (EOFError) is treated as 'no'.
    """
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "n"


def validate_recipient(to: str) -> tuple[bool, list[str]]:
    """Pure recipient validation (Guardrail 2 logic, no I/O).

    Returns ``(blocked, warnings)`` where ``blocked`` is True only for the hard
    rule (more than five recipients). Unknown contacts and typo'd domains are
    returned as warnings. Shared by the CLI and the web interface so both
    enforce identical rules.
    """
    recipients = [r.strip() for r in to.split(",") if r.strip()]
    warnings: list[str] = []
    blocked = False
    if len(recipients) > 5:
        blocked = True
        warnings.append(
            f"More than 5 recipients ({len(recipients)}); sending is blocked."
        )

    for recipient in recipients:
        _, addr = parseaddr(recipient)
        addr = addr or recipient
        if addr not in KNOWN_CONTACTS:
            warnings.append(f"Recipient not in known contacts: {addr}")
        domain = addr.split("@")[-1].lower() if "@" in addr else ""
        if any(typo in domain for typo in DOMAIN_TYPOS):
            warnings.append(f"Recipient domain looks like a typo: {domain}")
    return blocked, warnings


def check_content(subject: str, body: str) -> list[str]:
    """Pure content validation (Guardrail 3 logic, no I/O).

    Returns a list of human-readable warnings (empty if the content is clean).
    """
    warnings: list[str] = []
    if not subject.strip():
        warnings.append("Subject line is empty.")
    found = [token for token in PLACEHOLDER_TOKENS if token in body]
    if found:
        warnings.append(f"Body still contains placeholders: {', '.join(found)}")
    if len(body.strip()) < 30:
        warnings.append("Body is shorter than 30 characters.")
    return warnings


def _guardrail_recipient(to: str) -> bool:
    """Guardrail 2 — validate the recipient and print warnings (CLI).

    Returns False only for the hard block case (more than five recipients).
    """
    blocked, warnings = validate_recipient(to)
    for warning in warnings:
        color = RED if "typo" in warning or "blocked" in warning else YELLOW
        print(f"{color}[WARN] {warning}{RESET}")
    return not blocked


def _guardrail_content(subject: str, body: str) -> bool:
    """Guardrail 3 — content checks; prompt the operator on any warning (CLI)."""
    warnings = check_content(subject, body)
    if not warnings:
        return True
    for warning in warnings:
        print(f"{YELLOW}[WARN] {warning}{RESET}")
    return _confirm("Proceed anyway? [y/n] : ") == "y"


def _resolve_output_attachments(names: list[str] | None) -> tuple[list[str], list[str]]:
    """Resolve attachment file names to safe absolute paths inside outputs/.

    Returns ``(paths, missing)``. Only files that live directly in the project
    ``outputs/`` folder are accepted, to prevent path traversal from the web UI.
    """
    if not names:
        return [], []
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "outputs"
    )
    paths: list[str] = []
    missing: list[str] = []
    for name in names:
        base = os.path.basename(str(name)).strip()
        if not base:
            continue
        path = os.path.normpath(os.path.join(output_dir, base))
        if os.path.dirname(path) != os.path.normpath(output_dir):
            missing.append(base)
            continue
        if os.path.isfile(path):
            paths.append(path)
        else:
            missing.append(base)
    return paths, missing


def _attach_files(message: MIMEMultipart, paths: list[str]) -> None:
    """Attach each file in ``paths`` to a multipart email message."""
    for path in paths:
        with open(path, "rb") as handle:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(handle.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(path)}"',
        )
        message.attach(part)


def send_email_web(
    to: str,
    subject: str,
    body: str,
    dry_run: bool = True,
    attachments: list[str] | None = None,
) -> dict:
    """Non-interactive send for the web interface.

    The web "Send" click is treated as Guardrail 1 (explicit human
    confirmation), so this function runs Guardrails 2–4 programmatically and
    reports the outcome as a structured dict instead of prompting. Defaults to
    ``dry_run=True`` so the UI never sends by accident.

    Returns a dict: ``{sent, dry_run, blocked, rate_limited, warnings, message}``.
    """
    blocked, rec_warnings = validate_recipient(to)
    content_warnings = check_content(subject, body)
    warnings = rec_warnings + content_warnings

    attach_paths, missing = _resolve_output_attachments(attachments)
    if missing:
        warnings = warnings + [
            "Attachment not found, skipped: " + ", ".join(missing)
        ]

    result = {
        "sent": False,
        "dry_run": dry_run,
        "blocked": blocked,
        "rate_limited": False,
        "warnings": warnings,
        "attachments": [os.path.basename(p) for p in attach_paths],
        "message": "",
    }

    if blocked:
        result["message"] = "Blocked by recipient guardrail; not sent."
        return result

    if not _within_rate_limit():
        result["rate_limited"] = True
        result["message"] = (
            f"Rate limit reached ({MAX_SENDS} per "
            f"{RATE_WINDOW_SECONDS // 60} min); not sent."
        )
        return result

    if dry_run:
        result["sent"] = True
        suffix = (
            f" with {len(attach_paths)} attachment(s)" if attach_paths else ""
        )
        result["message"] = f"[DRY RUN] Would send to: {to}{suffix}"
        return result

    address = os.getenv("EMAIL_ADDRESS")
    app_password = os.getenv("APP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    if not address or not app_password:
        result["message"] = "EMAIL_ADDRESS / APP_PASSWORD not set; cannot send."
        return result

    if attach_paths:
        message = MIMEMultipart()
        message.attach(MIMEText(body, _charset="utf-8"))
        _attach_files(message, attach_paths)
    else:
        message = MIMEText(body, _charset="utf-8")
    message["From"] = address
    message["To"] = to
    message["Subject"] = subject
    try:
        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls()
            server.login(address, app_password)
            server.sendmail(address, to.split(","), message.as_string())
    except smtplib.SMTPAuthenticationError as error:
        result["message"] = f"SMTP authentication failed: {error}"
        return result
    except (smtplib.SMTPException, OSError) as error:
        result["message"] = f"SMTP error: {error}"
        return result

    _SEND_TIMESTAMPS.append(time.time())
    _append_sent_log(to, subject, body)
    result["sent"] = True
    suffix = f" with {len(attach_paths)} attachment(s)" if attach_paths else ""
    result["message"] = f"Email sent to {to}{suffix}."
    return result


def send_email(to: str, subject: str, body: str, dry_run: bool = False) -> bool:
    """Send an email through all four guardrails; return True if sent.

    Guardrail 1 (confirmation) is mandatory and cannot be bypassed. In
    dry-run mode SMTP is skipped entirely and the function reports what it
    would have sent.
    """
    # Guardrail 1 — mandatory human confirmation.
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}REVIEW OUTGOING EMAIL{RESET}")
    print(f"{'=' * 60}")
    print(f"To:      {to}")
    print(f"Subject: {subject}")
    print("-" * 60)
    print(body)
    print(f"{'=' * 60}")
    choice = _confirm("Send this email? [y]es / [n]o / [e]dit : ")
    if choice != "y":
        print(f"{GRAY}[guardrail] Not confirmed — email not sent.{RESET}")
        return False

    # Guardrail 2 — recipient validation (hard block possible).
    if not _guardrail_recipient(to):
        return False

    # Guardrail 3 — content checks.
    if not _guardrail_content(subject, body):
        print(f"{GRAY}[guardrail] Content warning declined — not sent.{RESET}")
        return False

    # Guardrail 4 — rate limiting.
    if not _within_rate_limit():
        print(f"{RED}[guardrail] Rate limit reached "
              f"({MAX_SENDS}/{RATE_WINDOW_SECONDS // 60} min). Not sent.{RESET}")
        return False

    if dry_run:
        print(f"{GREEN}[DRY RUN] Would send to: {to}{RESET}")
        return True

    address = os.getenv("EMAIL_ADDRESS")
    app_password = os.getenv("APP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    if not address or not app_password:
        print(f"{RED}[send] EMAIL_ADDRESS / APP_PASSWORD not set.{RESET}")
        return False

    message = MIMEText(body, _charset="utf-8")
    message["From"] = address
    message["To"] = to
    message["Subject"] = subject

    try:
        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls()
            server.login(address, app_password)
            server.sendmail(address, to.split(","), message.as_string())
    except smtplib.SMTPAuthenticationError as error:
        print(f"{RED}[send] SMTP authentication failed: {error}{RESET}")
        return False
    except (smtplib.SMTPException, OSError) as error:
        print(f"{RED}[send] SMTP error: {error}{RESET}")
        return False

    _SEND_TIMESTAMPS.append(time.time())
    _append_sent_log(to, subject, body)
    print(f"{GREEN}[send] Email sent to {to}.{RESET}")
    return True


def _append_sent_log(to: str, subject: str, body: str) -> None:
    """Append a single audit line to sent_log.txt."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    preview = body.replace("\n", " ")[:50]
    line = f"{timestamp} | {to} | {subject} | {preview}\n"
    try:
        with open(SENT_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError as error:
        print(f"{RED}[send] Failed to write sent_log.txt: {error}{RESET}")


def _open_in_editor(text: str) -> str:
    """Open ``text`` in the system editor and return the edited result.

    Falls back to returning the original text unchanged if no editor can be
    launched, so an editing failure never loses the draft.
    """
    editor = os.getenv("EDITOR") or ("notepad" if os.name == "nt" else "nano")
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(text)
            path = handle.name
        subprocess.call([editor, path])
        with open(path, "r", encoding="utf-8") as handle:
            edited = handle.read()
        os.unlink(path)
        return edited
    except Exception as error:  # noqa: BLE001 - editing is best-effort.
        print(f"{YELLOW}[edit] Could not open editor ({error}); "
              f"keeping original draft.{RESET}")
        return text


def _process_email(email_item: dict, memory: dict, dry_run: bool) -> str:
    """Draft a reply for one email and run the confirm/send loop.

    Returns one of: 'sent', 'skipped'. Memory and the rate limiter are updated
    as a side effect on a successful send.
    """
    sender = email_item.get("sender", "Unknown")
    subject = email_item.get("subject", "")
    print(f"\n{YELLOW}{'-' * 60}{RESET}")
    print(f"Processing [{email_item.get('triage_category')}] from {sender}")
    print(f"Subject: {subject}")
    print(f"Preview: {email_item.get('preview', '')}")

    draft = draft_email_reply(
        original_subject=subject,
        original_body=email_item.get("preview", ""),
        reply_intent="Acknowledge and provide the required response/next step.",
        project_context="CEM commercial construction project",
    )

    _, addr = parseaddr(sender)
    reply_to = addr or sender
    reply_subject = f"RE: {subject}"

    while True:
        result = send_email(reply_to, reply_subject, draft, dry_run=dry_run)
        if result:
            update_sender_profile(
                memory, reply_to, email_item.get("triage_category", "ACTION")
            )
            memory.setdefault("sent_history", []).append(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "to": reply_to,
                    "subject": reply_subject,
                    "category": email_item.get("triage_category", "ACTION"),
                }
            )
            return "sent"

        # Offer an edit pass before final skip.
        choice = _confirm("Re-try after [e]dit, or [s]kip? : ")
        if choice == "e":
            draft = _open_in_editor(draft)
            continue
        print(f"{GRAY}[agent] Skipped reply to {reply_to}.{RESET}")
        return "skipped"


def run_pipeline(
    use_test: bool = False, dry_run: bool = False, digest_only: bool = False
) -> None:
    """Execute the full agent pipeline end to end."""
    # Step 1 — startup header.
    print_header()

    # Step 2 — load memory.
    memory = load_memory()
    print(f"{GRAY}[agent] Memory loaded.{RESET}")

    # Step 3 — fetch + triage email.
    emails = fetch_recent_emails(use_test_data=use_test)
    print(f"{GRAY}[agent] Fetched {len(emails)} emails.{RESET}")

    # Step 4 — generate and print the digest.
    print()
    digest_text = generate_digest(emails)

    # Step 5 — Telegram alerts for every URGENT email.
    urgent = [e for e in emails if e.get("triage_category") == "URGENT"]
    for item in urgent:
        send_telegram_alert(
            subject=item.get("subject", ""),
            sender=item.get("sender", ""),
            preview=item.get("preview", ""),
        )

    if digest_only:
        save_memory(memory)
        print(f"\n{GRAY}[agent] Digest-only run complete.{RESET}")
        return

    # Step 6 — draft + confirm for each URGENT and ACTION email.
    to_process = [
        e for e in emails if e.get("triage_category") in ("URGENT", "ACTION")
    ]
    processed = sent = skipped = 0
    for item in to_process:
        outcome = _process_email(item, memory, dry_run=dry_run)
        processed += 1
        if outcome == "sent":
            sent += 1
        else:
            skipped += 1

    # Step 7 — run summary.
    stats = memory.setdefault("stats", {})
    stats["total_processed"] = stats.get("total_processed", 0) + processed
    stats["total_sent"] = stats.get("total_sent", 0) + sent
    stats["total_skipped"] = stats.get("total_skipped", 0) + skipped

    print(f"\n{BLUE}{'=' * 44}{RESET}")
    print(f"RUN SUMMARY: {processed} processed, {sent} sent, {skipped} skipped")
    print(f"{BLUE}{'=' * 44}{RESET}")

    # Step 8 — persist memory.
    save_memory(memory)
    print(f"{GRAY}[agent] Memory saved.{RESET}")


def main() -> None:
    """Parse CLI flags and dispatch the appropriate pipeline run."""
    parser = argparse.ArgumentParser(
        description="CEM501 AI Communication Agent pipeline."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run the full pipeline but never actually send email.",
    )
    parser.add_argument(
        "--digest-only", action="store_true",
        help="Fetch and produce the digest only; skip drafting/sending.",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Use hardcoded test emails instead of a live inbox.",
    )
    args = parser.parse_args()

    try:
        run_pipeline(
            use_test=args.test,
            dry_run=args.dry_run,
            digest_only=args.digest_only,
        )
    except KeyboardInterrupt:
        print(f"\n{GRAY}[agent] Interrupted by user. Exiting.{RESET}")
        sys.exit(130)


if __name__ == "__main__":
    main()
