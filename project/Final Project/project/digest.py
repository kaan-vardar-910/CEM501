"""Daily morning digest generator (Milestone M3).

Turns a list of triaged emails into the single screen a project manager reads
with their coffee: urgent and action items get a one-sentence LLM summary,
FYIs are listed by subject, and archive mail is reduced to a count. Summaries
are only generated for the categories that matter, to save tokens.
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parseaddr

from reader import fetch_recent_emails
from templates import summarize_with_action

try:
    from contacts import get_importance
except ImportError:  # pragma: no cover - contacts module always present
    def get_importance(_email: str) -> str:
        return "normal"

# Categories that justify spending an LLM call on a per-email summary.
SUMMARY_CATEGORIES = ("URGENT", "ACTION")


def _test_emails() -> list[dict]:
    """Return six generic CEM emails for credential-free digest testing."""
    return [
        {
            "sender": "Safety Inspector <inspector@example.com>",
            "subject": "Fall protection deficiency — immediate correction",
            "date": "2026-06-06",
            "preview": (
                "A fall protection deficiency was observed on the east leading "
                "edge this morning. Work in that area must stop until guardrails "
                "are reinstalled and re-inspected."
            ),
            "triage_category": "URGENT",
        },
        {
            "sender": "Owner Representative <owner@example.com>",
            "subject": "Notice of liquidated damages — milestone at risk",
            "date": "2026-06-06",
            "preview": (
                "Per the contract, liquidated damages will accrue if the "
                "substantial completion milestone is missed. Please advise on "
                "the recovery plan by end of week."
            ),
            "triage_category": "URGENT",
        },
        {
            "sender": "Project Architect <architect@example.com>",
            "subject": "RFI-047 response needed — rebar spacing",
            "date": "2026-06-06",
            "preview": (
                "We need your response on RFI-047 regarding the rebar spacing "
                "discrepancy at the pile cap so the pour can proceed on "
                "schedule."
            ),
            "triage_category": "ACTION",
        },
        {
            "sender": "Engineer of Record <eor@example.com>",
            "subject": "Submittal review request — structural steel",
            "date": "2026-06-06",
            "preview": (
                "Please review and return the structural steel submittal "
                "package. Approval is required before fabrication can be "
                "released."
            ),
            "triage_category": "ACTION",
        },
        {
            "sender": "Project Scheduler <scheduler@example.com>",
            "subject": "Weekly progress update — 2 days ahead of baseline",
            "date": "2026-06-06",
            "preview": (
                "The project is tracking two days ahead of baseline with no "
                "critical-path concerns this week."
            ),
            "triage_category": "FYI",
        },
        {
            "sender": "BuildSupply Marketing <sales@buildsupply.example>",
            "subject": "Summer sale on safety gear — 20% off",
            "date": "2026-06-06",
            "preview": (
                "Stock up now on hard hats, vests and harnesses with 20% off "
                "through the end of the month."
            ),
            "triage_category": "ARCHIVE",
        },
    ]


def _group_by_category(emails: list[dict]) -> dict[str, list[dict]]:
    """Bucket emails into the four triage categories."""
    groups: dict[str, list[dict]] = {
        "URGENT": [],
        "ACTION": [],
        "FYI": [],
        "ARCHIVE": [],
    }
    for item in emails:
        category = item.get("triage_category", "ARCHIVE")
        groups.setdefault(category, []).append(item)
    return groups


def build_digest_data(emails: list[dict]) -> dict:
    """Return a structured digest used by both the text and HTML renderers.

    URGENT/ACTION emails get a one-sentence LLM summary (computed once here);
    every email is tagged with its sender's contact importance so the UI can
    colour-code and flag VIP/urgent senders. Action items are derived from the
    URGENT and ACTION buckets so the PM has a single to-do list.
    """
    groups = _group_by_category(emails)
    now = datetime.now()

    categories: dict[str, list[dict]] = {
        "URGENT": [],
        "ACTION": [],
        "FYI": [],
    }
    actions: list[dict] = []
    flagged: dict[str, dict] = {}

    for category in ("URGENT", "ACTION", "FYI"):
        for item in groups.get(category, []):
            sender = item.get("sender", "Unknown")
            name, addr = parseaddr(sender)
            importance = get_importance(addr) if addr else "normal"
            entry = {
                "sender": sender,
                "name": name or addr or sender,
                "email": addr,
                "subject": item.get("subject", ""),
                "importance": importance,
                "summary": "",
                "suggested_action": "",
            }
            if category in SUMMARY_CATEGORIES:
                result = summarize_with_action(
                    item.get("body") or item.get("preview", "")
                )
                summary = result.get("summary", "")
                suggested = result.get("action", "")
                entry["summary"] = summary
                entry["suggested_action"] = suggested
                actions.append(
                    {
                        "category": category,
                        "sender": sender,
                        "name": entry["name"],
                        "subject": entry["subject"],
                        "summary": summary,
                        "suggested_action": suggested,
                        "importance": importance,
                    }
                )
            categories[category].append(entry)

            if importance in ("vip", "urgent") and addr and addr not in flagged:
                flagged[addr] = {
                    "name": entry["name"],
                    "email": addr,
                    "importance": importance,
                }

    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "total": len(emails),
        "counts": {
            "URGENT": len(groups.get("URGENT", [])),
            "ACTION": len(groups.get("ACTION", [])),
            "FYI": len(groups.get("FYI", [])),
            "ARCHIVE": len(groups.get("ARCHIVE", [])),
        },
        "categories": categories,
        "actions": actions,
        "flagged_contacts": list(flagged.values()),
    }


def render_digest_text(data: dict) -> str:
    """Render the plain-text digest (for console, Telegram and logs) from data."""
    counts = data["counts"]
    lines: list[str] = []

    lines.append("=" * 44)
    lines.append("=== PROJECT MORNING DIGEST ===")
    lines.append(f"Generated: {data['date']} at {data['time']}")
    lines.append(f"Covering: {data['total']} emails")
    lines.append("=" * 44)
    lines.append("")

    flagged = data.get("flagged_contacts", [])
    if flagged:
        lines.append("!!! VIP / URGENT CONTACTS IN THIS BATCH !!!")
        for contact in flagged:
            lines.append(
                f"  * {contact['name']} <{contact['email']}> "
                f"[{contact['importance'].upper()}]"
            )
        lines.append("")

    actions = data.get("actions", [])
    lines.append(f">>> ACTION ITEMS ({len(actions)}) <<<")
    if actions:
        for index, action in enumerate(actions, start=1):
            lines.append(
                f"{index}. [{action['category']}] {action['subject']} "
                f"— {action['name']}"
            )
            lines.append(f"    Summary: {action['summary']}")
            if action.get("suggested_action"):
                lines.append(f"    Recommended: {action['suggested_action']}")
    else:
        lines.append("  (none)")
    lines.append("")

    for category in ("URGENT", "ACTION"):
        bucket = data["categories"].get(category, [])
        lines.append(f"--- {category} ({len(bucket)}) ---")
        for index, item in enumerate(bucket, start=1):
            tag = (
                f" [{item['importance'].upper()}]"
                if item["importance"] in ("vip", "urgent")
                else ""
            )
            lines.append(f"{index}. From: {item['sender']}{tag}")
            lines.append(f"    Subject: {item['subject']}")
            lines.append(f"    Summary: {item['summary']}")
            if item.get("suggested_action"):
                lines.append(f"    Recommended: {item['suggested_action']}")
        lines.append("")

    fyi = data["categories"].get("FYI", [])
    lines.append(f"--- FYI ({len(fyi)}) ---")
    for item in fyi:
        lines.append(f"  - {item['subject']}")
    lines.append("")

    lines.append(f"--- ARCHIVE ({counts['ARCHIVE']} emails skipped) ---")
    lines.append("")

    lines.append("=" * 44)
    lines.append("REMINDER: AI summaries are drafts, not official records.")
    lines.append("Always read the original email before taking action.")
    lines.append("=" * 44)

    return "\n".join(lines)


def generate_digest(emails: list[dict]) -> str:
    """Build, print and return the formatted morning digest text."""
    data = build_digest_data(emails)
    digest = render_digest_text(data)
    print(digest)
    return digest


if __name__ == "__main__":
    # Credential-free demonstration with six hardcoded test emails.
    # Summaries require ANTHROPIC_API_KEY; without it each summary line will
    # show a clear error string but the digest layout still renders.
    generate_digest(_test_emails())
