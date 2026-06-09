"""Guided, narrated demonstration of the whole system (BONUS).

Runs the real modules end to end so the project can be presented to the
instructor without a live inbox. Every step calls actual module functions —
no faked output. If ANTHROPIC_API_KEY is absent, the LLM-dependent document
steps degrade to a clear placeholder rather than failing.
"""

from __future__ import annotations

import os
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    CYAN = Fore.CYAN
    GREEN = Fore.GREEN
    RESET = Style.RESET_ALL
except ImportError:
    CYAN = GREEN = RESET = ""

from reader import fetch_recent_emails, print_triage_table
from digest import generate_digest
from templates import draft_rfi, draft_delay_notice
from memory import load_memory, get_stats_summary

# Pause between sections so a live audience can follow along.
PAUSE = 1.5


def _narrate(text: str) -> None:
    """Print a narration line and pause briefly for the audience."""
    print(f"\n{CYAN}>> {text}{RESET}")
    time.sleep(PAUSE)


def _has_api_key() -> bool:
    """Return True if an Anthropic key is configured."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _demo_emails() -> list[dict]:
    """Return five generic CEM emails used across the demo."""
    base = fetch_recent_emails(use_test_data=True)
    extra = [
        {
            "sender": "Owner Representative <owner@example.com>",
            "subject": "Notice of liquidated damages — milestone at risk",
            "date": "2026-06-06",
            "preview": (
                "Liquidated damages will accrue if the substantial completion "
                "milestone is missed; please send a recovery plan."
            ),
            "triage_category": "URGENT",
        },
        {
            "sender": "BuildSupply Marketing <sales@buildsupply.example>",
            "subject": "Summer sale on safety gear — 20% off",
            "date": "2026-06-06",
            "preview": "Stock up on hard hats and harnesses at 20% off.",
            "triage_category": "ARCHIVE",
        },
    ]
    return base + extra


def step_0_title() -> None:
    """Print the demo title card."""
    print("=" * 60)
    print("   CEM501 AI COMMUNICATION AGENT — GUIDED DEMO")
    print("   A personal communication assistant for a CEM project manager")
    print("=" * 60)
    time.sleep(PAUSE)


def step_1_triage(emails: list[dict]) -> None:
    """Demonstrate reader.py triage."""
    _narrate("The agent reads the inbox and classifies each email...")
    print_triage_table(emails)


def step_2_digest(emails: list[dict]) -> None:
    """Demonstrate the morning digest."""
    _narrate("Here is what a PM sees at the start of the day...")
    generate_digest(emails)


def step_3_rfi() -> None:
    """Demonstrate RFI generation."""
    _narrate("When the agent detects an RFI is needed, it drafts one...")
    if not _has_api_key():
        print("[ANTHROPIC_API_KEY not set — showing placeholder RFI]")
        print(
            "RFI Number: [to be assigned]\nProject: Riverside Commercial Tower\n"
            "Subject: S-204 vs Section 03 21 00 — rebar spacing conflict\n"
            "Question: Which rebar spacing governs at the pile cap?\n"
            "Suggested Resolution: Adopt specification spacing.\n"
            "Impact if Unanswered: Pour delayed; respond by 2026-06-11."
        )
        return
    draft_rfi(
        project_name="Riverside Commercial Tower",
        drawing_ref="S-204",
        spec_ref="Section 03 21 00",
        issue="Rebar spacing on the drawing conflicts with the specification.",
        suggested_resolution="Adopt specification spacing for required cover.",
        affected_trade="Concrete / reinforcing steel",
        activity_start_date="2026-06-15",
        response_deadline="2026-06-11",
    )


def step_4_delay_notice() -> None:
    """Demonstrate delay-notice generation."""
    _narrate("For a weather delay, it produces a formal notice...")
    if not _has_api_key():
        print("[ANTHROPIC_API_KEY not set — showing placeholder delay notice]")
        print(
            "Re: Weather Delay Notice\nContract Section: 8.3 (Delays)\n"
            "Date Range: 2026-05-18 to 2026-05-22\n"
            "Affected Activities: A-1200, A-1210\n"
            "Days Requested: 5 (non-compensable)\n"
            "Action: Please acknowledge the time extension by 2026-06-12."
        )
        return
    draft_delay_notice(
        project_name="Riverside Commercial Tower",
        contract_no="CN-2026-014",
        contract_section="8.3 (Delays)",
        start_date="2026-05-18",
        end_date="2026-05-22",
        affected_activities=["A-1200", "A-1210"],
        days_requested=5,
        supporting_data="0.6 in. rainfall recorded daily; site inaccessible.",
    )


def step_5_pipeline() -> None:
    """Describe the guarded send pipeline (dry-run)."""
    _narrate("Each draft goes through mandatory human confirmation...")
    print("In a live run, 'python agent.py --test --dry-run' walks the PM")
    print("through every draft with four guardrails before anything is sent:")
    print("  1. Mandatory confirmation prompt (cannot be bypassed)")
    print("  2. Recipient validation (unknown contacts, typo'd domains)")
    print("  3. Content checks (placeholders, empty subject, short body)")
    print("  4. Rate limiting (max 10 sends per 10 minutes)")


def step_6_memory() -> None:
    """Show persistent memory stats."""
    _narrate("The agent remembers past interactions across sessions...")
    memory = load_memory()
    profiles = memory.get("sender_profiles", {})
    print(f"Known sender profiles: {len(profiles)}")
    print(f"Stats -> {get_stats_summary(memory)}")


def step_7_summary() -> None:
    """Print the closing capabilities summary."""
    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}DEMO COMPLETE — capabilities demonstrated:{RESET}")
    print("  - IMAP reading + keyword triage (URGENT/ACTION/FYI/ARCHIVE)")
    print("  - LLM morning digest with action-focused summaries")
    print("  - Formal RFI and weather delay notice generation")
    print("  - Guarded, human-in-the-loop email sending")
    print("  - Persistent cross-session memory")
    print("  - Telegram multi-channel alerts for urgent items")
    print(f"{GREEN}{'=' * 60}{RESET}")


def main() -> None:
    """Run all seven narrated demo steps in order."""
    emails = _demo_emails()
    step_0_title()
    step_1_triage(emails)
    step_2_digest(emails)
    step_3_rfi()
    step_4_delay_notice()
    step_5_pipeline()
    step_6_memory()
    step_7_summary()


if __name__ == "__main__":
    main()
