"""IMAP email reader and keyword triage engine (Milestone M2).

Connects to Gmail over IMAP, fetches the most recent messages, extracts the
fields the agent cares about, and assigns each message a triage category using
deterministic keyword rules. The same triage logic powers the digest and the
full pipeline, so it is intentionally simple, fast and explainable.
"""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
from email.header import decode_header
from email.utils import parseaddr
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional for test-data runs.
    pass

import contacts as contacts_book

# Colour handling with a graceful no-colour fallback (Section 8 pattern).
try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    BLUE = Fore.BLUE
    RESET = Style.RESET_ALL
    GRAY = Fore.WHITE
except ImportError:
    RED = YELLOW = BLUE = RESET = GRAY = ""

# --- Triage configuration -------------------------------------------------
# Keyword sets are checked highest-severity first so the most consequential
# category always wins when an email matches several at once. The DEFAULT_*
# lists below are the factory settings; the active lists can be overridden at
# runtime via triage_config.json so the UI Settings tab can edit them without
# touching the code.
DEFAULT_URGENT_KEYWORDS = [
    "stop work", "safety", "incident", "notice of delay", "urgent",
    "claim", "time-bar", "liquidated", "immediate", "emergency",
    "fall protection", "osha",
]
DEFAULT_ACTION_KEYWORDS = [
    "rfi", "submittal", "review", "approval", "change order",
    "schedule", "response required", "action", "please confirm",
    "deadline", "expire",
]
DEFAULT_FYI_KEYWORDS = [
    "update", "recap", "photos", "minutes", "weekly", "daily log",
    "fyi", "newsletter", "summary", "progress",
]
# Senders whose display name contains any of these are always at least ACTION.
DEFAULT_KNOWN_VIP = [
    "owner", "inspector", "osha", "municipality", "architect",
    "engineer of record",
]

# Where user-edited triage settings are persisted (next to this module).
TRIAGE_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "triage_config.json"
)

# Active keyword sets. These are mutated in place by reload_triage_config()
# so that triage_email always sees the latest settings without a restart.
URGENT_KEYWORDS = list(DEFAULT_URGENT_KEYWORDS)
ACTION_KEYWORDS = list(DEFAULT_ACTION_KEYWORDS)
FYI_KEYWORDS = list(DEFAULT_FYI_KEYWORDS)
KNOWN_VIP = list(DEFAULT_KNOWN_VIP)


def _normalize_keywords(values: object) -> list[str]:
    """Lower-case, trim and de-duplicate a list of keyword strings.

    Tolerant of bad input (non-lists, blanks) so a hand-edited config or an
    odd UI payload can never produce a broken keyword set.
    """
    result: list[str] = []
    if isinstance(values, str):
        values = values.replace("\n", ",").split(",")
    if not isinstance(values, (list, tuple)):
        return result
    for value in values:
        text = str(value).strip().lower()
        if text and text not in result:
            result.append(text)
    return result


def get_triage_config() -> dict:
    """Return the currently active triage configuration as a dict."""
    return {
        "urgent": list(URGENT_KEYWORDS),
        "action": list(ACTION_KEYWORDS),
        "fyi": list(FYI_KEYWORDS),
        "vip": list(KNOWN_VIP),
    }


def get_default_triage_config() -> dict:
    """Return the factory-default triage configuration as a dict."""
    return {
        "urgent": list(DEFAULT_URGENT_KEYWORDS),
        "action": list(DEFAULT_ACTION_KEYWORDS),
        "fyi": list(DEFAULT_FYI_KEYWORDS),
        "vip": list(DEFAULT_KNOWN_VIP),
    }


def reload_triage_config() -> dict:
    """Load triage_config.json (if present) into the active keyword lists.

    Mutates the module-level lists in place so existing references stay valid.
    Falls back to factory defaults for any missing or unreadable section.
    """
    data: dict = {}
    if os.path.exists(TRIAGE_CONFIG_PATH):
        try:
            with open(TRIAGE_CONFIG_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError) as error:
            print(f"[reader] Could not read triage config: {error}")
            data = {}

    URGENT_KEYWORDS[:] = (
        _normalize_keywords(data.get("urgent")) or list(DEFAULT_URGENT_KEYWORDS)
    )
    ACTION_KEYWORDS[:] = (
        _normalize_keywords(data.get("action")) or list(DEFAULT_ACTION_KEYWORDS)
    )
    FYI_KEYWORDS[:] = (
        _normalize_keywords(data.get("fyi")) or list(DEFAULT_FYI_KEYWORDS)
    )
    KNOWN_VIP[:] = (
        _normalize_keywords(data.get("vip")) or list(DEFAULT_KNOWN_VIP)
    )
    return get_triage_config()


def save_triage_config(config: dict) -> dict:
    """Persist a new triage configuration and apply it immediately.

    Empty sections fall back to the factory defaults so the agent can never end
    up with, say, zero urgent keywords. Returns the now-active configuration.
    """
    payload = {
        "urgent": _normalize_keywords(config.get("urgent"))
        or list(DEFAULT_URGENT_KEYWORDS),
        "action": _normalize_keywords(config.get("action"))
        or list(DEFAULT_ACTION_KEYWORDS),
        "fyi": _normalize_keywords(config.get("fyi"))
        or list(DEFAULT_FYI_KEYWORDS),
        "vip": _normalize_keywords(config.get("vip"))
        or list(DEFAULT_KNOWN_VIP),
    }
    try:
        with open(TRIAGE_CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
    except OSError as error:
        print(f"[reader] Failed to save triage config: {error}")
    return reload_triage_config()

# In-memory map of {email -> importance} so triage_email can apply contact
# overrides without hitting disk for every message during a fetch.
_CONTACT_IMPORTANCE: dict[str, str] = {}


def reload_contacts_cache() -> dict[str, str]:
    """Refresh the email->importance cache from contacts.json."""
    global _CONTACT_IMPORTANCE
    cache: dict[str, str] = {}
    for contact in contacts_book.load_contacts().get("contacts", []):
        cache[contact["email"]] = contact.get("importance", "normal")
    _CONTACT_IMPORTANCE = cache
    return cache


# Apply any persisted user settings as soon as the module is imported.
reload_triage_config()
reload_contacts_cache()

# Triage ordering used when sorting the output table.
CATEGORY_ORDER = {"URGENT": 0, "ACTION": 1, "FYI": 2, "ARCHIVE": 3}
CATEGORY_COLORS = {
    "URGENT": RED,
    "ACTION": YELLOW,
    "FYI": BLUE,
    "ARCHIVE": GRAY,
}


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace from a body string."""
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", no_tags).strip()


def _decode_mime(raw: Optional[str]) -> str:
    """Decode an RFC 2047 encoded header (subject/sender) to plain text."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = ""
    for value, charset in parts:
        if isinstance(value, bytes):
            try:
                decoded += value.decode(charset or "utf-8", errors="replace")
            except (LookupError, TypeError):
                decoded += value.decode("utf-8", errors="replace")
        else:
            decoded += value
    return decoded.strip()


def _matches_any(haystack: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears as a whole word in ``haystack``.

    Word-boundary matching avoids false positives such as the sender word
    "Scheduler" triggering the ACTION keyword "schedule", while still matching
    tokens like "RFI" inside "RFI-047" (the hyphen is a word boundary).
    """
    return any(
        re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in keywords
    )


def triage_email(sender: str, subject: str) -> str:
    """Classify an email into URGENT / ACTION / FYI / ARCHIVE.

    Matching is case-insensitive whole-word matching on the combined
    sender+subject string. A VIP sender can only elevate the floor to ACTION;
    it never downgrades a message that already scored URGENT.
    """
    haystack = f"{sender} {subject}".lower()

    if _matches_any(haystack, URGENT_KEYWORDS):
        category = "URGENT"
    elif _matches_any(haystack, ACTION_KEYWORDS):
        category = "ACTION"
    elif _matches_any(haystack, FYI_KEYWORDS):
        category = "FYI"
    else:
        category = "ARCHIVE"

    sender_lower = sender.lower()
    is_vip = any(vip in sender_lower for vip in KNOWN_VIP)
    if is_vip and CATEGORY_ORDER[category] > CATEGORY_ORDER["ACTION"]:
        # VIP raises the floor to ACTION but cannot demote an URGENT email.
        category = "ACTION"

    # Contact-book overrides take precedence over keyword results: an "urgent"
    # contact is always URGENT; a "vip" contact is at least ACTION.
    sender_email = parseaddr(sender)[1].lower()
    importance = _CONTACT_IMPORTANCE.get(sender_email)
    if importance == "urgent":
        category = "URGENT"
    elif importance == "vip" and CATEGORY_ORDER[category] > CATEGORY_ORDER["ACTION"]:
        category = "ACTION"
    return category


def _extract_body_text(message: email.message.Message) -> str:
    """Return the full plain-text body of a message, HTML stripped.

    Prefers a text/plain part; falls back to the first text/html part. Used both
    for the short preview and for the full body that feeds LLM summaries, so the
    summariser never sees a truncated email.
    """
    body = ""
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if content_type == "text/plain" and "attachment" not in disposition:
                body = _payload_to_text(part)
                if body:
                    break
        if not body:
            # Fall back to HTML if no plain-text part was present.
            for part in message.walk():
                if part.get_content_type() == "text/html":
                    body = _strip_html(_payload_to_text(part))
                    break
    else:
        body = _payload_to_text(message)
        if message.get_content_type() == "text/html":
            body = _strip_html(body)

    return re.sub(r"\s+", " ", body).strip()


def _payload_to_text(part: email.message.Message) -> str:
    """Decode a single message part's payload into a string safely."""
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except (LookupError, ValueError, TypeError):
        return ""


def _test_emails() -> list[dict]:
    """Return three generic CEM emails for credential-free testing."""
    return [
        {
            "sender": "Safety Inspector <inspector@example.com>",
            "subject": (
                "Fall protection deficiency — immediate correction required"
            ),
            "date": "Mon, 06 Jun 2026 07:15:00 +0300",
            "preview": (
                "During this morning's walk a fall protection deficiency was "
                "observed on the east leading edge. Immediate correction is "
                "required before work resumes."
            ),
            "triage_category": "",
        },
        {
            "sender": "Project Architect <architect@example.com>",
            "subject": "RFI-047: Rebar spacing discrepancy — response needed",
            "date": "Mon, 06 Jun 2026 08:02:00 +0300",
            "preview": (
                "We have identified a rebar spacing discrepancy between the "
                "structural drawings and the project specification. A response "
                "is needed to keep the pile cap pour on schedule."
            ),
            "triage_category": "",
        },
        {
            "sender": "Project Scheduler <scheduler@example.com>",
            "subject": "Weekly progress update — 2 days ahead of baseline",
            "date": "Mon, 06 Jun 2026 08:30:00 +0300",
            "preview": (
                "Weekly progress summary: the project is currently tracking "
                "two days ahead of the baseline schedule. No critical path "
                "issues to report this week."
            ),
            "triage_category": "",
        },
    ]


def _capture_senders(emails: list[dict]) -> None:
    """Auto-save every sender as a contact and refresh the importance cache.

    New senders are stored as 'normal'; existing classifications are preserved.
    """
    senders: list[tuple[str, str]] = []
    for item in emails:
        raw = item.get("sender", "")
        display, addr = parseaddr(raw)
        if addr:
            senders.append((display or addr, addr))
    if senders:
        contacts_book.bulk_upsert_senders(senders)
        reload_contacts_cache()


def fetch_recent_emails(count: int = 20, use_test_data: bool = False) -> list[dict]:
    """Fetch and triage the ``count`` most recent emails.

    When ``use_test_data`` is True, returns three hardcoded generic CEM emails
    so the module can be demonstrated without any credentials. Otherwise it
    connects to the configured IMAP server, fetches the latest messages and
    triages each one. The IMAP connection is always closed in a finally block.

    Returns a list of dicts with keys: sender, subject, date, preview,
    triage_category.
    """
    if use_test_data:
        emails = _test_emails()
        _capture_senders(emails)
        for item in emails:
            # Test previews are already complete; mirror them as the full body.
            item.setdefault("body", item.get("preview", ""))
            item["triage_category"] = triage_email(item["sender"], item["subject"])
        return emails

    address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")

    if not address or not password:
        print(
            f"{YELLOW}[reader] EMAIL_ADDRESS / EMAIL_PASSWORD not set. "
            f"Falling back to test data.{RESET}"
        )
        return fetch_recent_emails(count=count, use_test_data=True)

    connection: Optional[imaplib.IMAP4_SSL] = None
    results: list[dict] = []
    try:
        connection = imaplib.IMAP4_SSL(imap_server, 993)
        connection.login(address, password)
        connection.select("INBOX")

        status, data = connection.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            print(f"{GRAY}[reader] Inbox is empty.{RESET}")
            return []

        ids = data[0].split()
        recent_ids = ids[-count:][::-1]  # newest first

        for msg_id in recent_ids:
            status, msg_data = connection.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data:
                continue
            raw = msg_data[0][1]
            message = email.message_from_bytes(raw)

            display, addr = parseaddr(message.get("From", ""))
            display = _decode_mime(display) or addr
            sender = f"{display} <{addr}>" if addr else display
            subject = _decode_mime(message.get("Subject", ""))
            date = message.get("Date", "")
            full_body = _extract_body_text(message)
            preview = full_body[:200].strip()
            category = triage_email(sender, subject)

            results.append(
                {
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "preview": preview,
                    "body": full_body,
                    "triage_category": category,
                }
            )
    except imaplib.IMAP4.error as error:
        print(f"{RED}[reader] IMAP/authentication error: {error}{RESET}")
    except OSError as error:
        print(f"{RED}[reader] Connection error: {error}{RESET}")
    finally:
        if connection is not None:
            try:
                connection.close()
            except imaplib.IMAP4.error:
                pass
            try:
                connection.logout()
            except imaplib.IMAP4.error:
                pass

    _capture_senders(results)
    return results


def print_triage_table(emails: list[dict]) -> None:
    """Print a colour-coded, severity-sorted triage table to the terminal."""
    if not emails:
        print(f"{GRAY}No emails to display.{RESET}")
        return

    ordered = sorted(
        emails, key=lambda item: CATEGORY_ORDER.get(item["triage_category"], 99)
    )

    print("=" * 78)
    print(f"{'CATEGORY':<9} {'FROM':<32} SUBJECT")
    print("-" * 78)
    for item in ordered:
        category = item["triage_category"]
        color = CATEGORY_COLORS.get(category, GRAY)
        sender = item["sender"][:30]
        subject = item["subject"][:34]
        print(f"{color}{category:<9} {sender:<32} {subject}{RESET}")
    print("=" * 78)
    print(f"Total: {len(emails)} emails")


if __name__ == "__main__":
    # Credential-free demonstration using the three hardcoded test emails.
    print("Fetching test emails (no credentials required)...\n")
    sample = fetch_recent_emails(use_test_data=True)
    print_triage_table(sample)
