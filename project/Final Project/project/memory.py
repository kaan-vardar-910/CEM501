"""Persistent JSON memory for the CEM501 agent (BONUS module).

Gives the agent recall across sessions: which senders typically send urgent
mail, what has already been sent, and where the user has corrected the
automatic triage. Storage is a single human-readable JSON file so it can be
inspected and edited by hand during a demo without any database tooling.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

# Memory lives next to this module so the path is stable regardless of the
# working directory the agent is launched from.
MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")


def _default_memory() -> dict:
    """Return a fresh, empty memory structure.

    Centralised here so every consumer agrees on the schema and missing keys
    can be back-filled when an older file is loaded.
    """
    return {
        "sender_profiles": {},
        "sent_history": [],
        "user_corrections": [],
        "stats": {
            "total_processed": 0,
            "total_sent": 0,
            "total_skipped": 0,
        },
    }


def load_memory() -> dict:
    """Load ``memory.json`` and return it as a dict.

    Returns the default empty structure if the file does not exist or is
    corrupt, so a missing/garbled file can never crash the agent.
    """
    if not os.path.exists(MEMORY_PATH):
        return _default_memory()
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as error:
        print(f"[memory] Could not read memory file, starting fresh: {error}")
        return _default_memory()

    # Back-fill any keys an older or hand-edited file may be missing.
    defaults = _default_memory()
    for key, value in defaults.items():
        data.setdefault(key, value)
    for key, value in defaults["stats"].items():
        data["stats"].setdefault(key, value)
    return data


def save_memory(memory: dict) -> None:
    """Write ``memory`` to ``memory.json`` with indent=2.

    Errors are reported but never raised: a failed save must not abort an
    otherwise successful agent run.
    """
    try:
        with open(MEMORY_PATH, "w", encoding="utf-8") as handle:
            json.dump(memory, handle, indent=2, ensure_ascii=False)
    except OSError as error:
        print(f"[memory] Failed to save memory: {error}")


def update_sender_profile(memory: dict, sender: str, category: str) -> dict:
    """Create or update the profile for ``sender`` and return ``memory``.

    Increments the running email count, records today's date as last seen and
    keeps the most recent triage category as the sender's typical category.
    """
    profiles = memory.setdefault("sender_profiles", {})
    profile = profiles.get(sender)
    today = datetime.now().strftime("%Y-%m-%d")

    if profile is None:
        profiles[sender] = {
            "name": sender,
            "typical_category": category,
            "email_count": 1,
            "last_seen": today,
            "notes": "",
        }
    else:
        profile["email_count"] = profile.get("email_count", 0) + 1
        profile["last_seen"] = today
        # The latest observed category is the best cheap predictor.
        profile["typical_category"] = category
    return memory


def get_sender_category_hint(memory: dict, sender: str) -> Optional[str]:
    """Return the typical category for a known sender, else ``None``."""
    profile = memory.get("sender_profiles", {}).get(sender)
    if profile is None:
        return None
    return profile.get("typical_category")


def log_correction(
    memory: dict, subject: str, auto: str, correct: str, reason: str
) -> dict:
    """Record a user correction of the automatic triage and return ``memory``.

    These entries are the training signal a future ML-based classifier would
    learn from, and they document why a human overrode the agent.
    """
    memory.setdefault("user_corrections", []).append(
        {
            "email_subject": subject,
            "auto_category": auto,
            "correct_category": correct,
            "reason": reason,
        }
    )
    return memory


def get_stats_summary(memory: dict) -> str:
    """Return a one-line formatted stats summary."""
    stats = memory.get("stats", {})
    processed = stats.get("total_processed", 0)
    sent = stats.get("total_sent", 0)
    skipped = stats.get("total_skipped", 0)
    return f"Processed: {processed} | Sent: {sent} | Skipped: {skipped}"


if __name__ == "__main__":
    # Smoke test: exercise every function without needing real data.
    mem = load_memory()
    mem = update_sender_profile(mem, "inspector@example.com", "URGENT")
    mem = update_sender_profile(mem, "inspector@example.com", "URGENT")
    hint = get_sender_category_hint(mem, "inspector@example.com")
    print(f"Sender hint for inspector@example.com: {hint}")
    mem = log_correction(
        mem,
        "Updated delivery schedule",
        "ARCHIVE",
        "ACTION",
        "Delivery changes affect critical path",
    )
    print(get_stats_summary(mem))
    print("Memory module self-test complete (not saved).")
