"""Sender profiles / signature management (BONUS — identity settings).

Stores one or more sender profiles (name, title, company, phone, email) in a
JSON file and tracks which one is active. The active profile's formatted
signature is injected into every generated draft so documents and replies are
signed automatically with real contact details instead of LLM placeholders.
"""

from __future__ import annotations

import json
import os
from typing import Optional

PROFILES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "profiles_config.json"
)

# Fields a profile may contain; order matters for the rendered signature.
# ``project`` is the operator's default project name (auto-filled into the
# document forms); ``site_city``/``site_lat``/``site_lng`` hold the project
# location used for Daily Report auto-weather. None of these are part of the
# signature block.
PROFILE_FIELDS = (
    "first_name",
    "last_name",
    "title",
    "company",
    "phone",
    "email",
    "project",
    "site_city",
    "site_lat",
    "site_lng",
)


def _default_profiles() -> dict:
    """Return the empty default structure (no profiles, active index 0)."""
    return {"active": 0, "profiles": []}


def _clean_profile(raw: object) -> dict:
    """Coerce an arbitrary dict into a profile with all expected string fields."""
    profile = {field: "" for field in PROFILE_FIELDS}
    if isinstance(raw, dict):
        for field in PROFILE_FIELDS:
            value = raw.get(field, "")
            profile[field] = str(value).strip() if value is not None else ""
    return profile


def load_profiles() -> dict:
    """Load profiles_config.json, returning the default structure on any error."""
    if not os.path.exists(PROFILES_PATH):
        return _default_profiles()
    try:
        with open(PROFILES_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as error:
        print(f"[profiles] Could not read profiles: {error}")
        return _default_profiles()

    profiles = [_clean_profile(p) for p in data.get("profiles", [])]
    active = data.get("active", 0)
    if not isinstance(active, int) or not (0 <= active < len(profiles)):
        active = 0
    return {"active": active, "profiles": profiles}


def save_profiles(data: dict) -> dict:
    """Persist profiles and active selection; return the cleaned structure."""
    profiles = [_clean_profile(p) for p in data.get("profiles", [])]
    active = data.get("active", 0)
    if not isinstance(active, int) or not (0 <= active < len(profiles)):
        active = 0 if profiles else 0
    payload = {"active": active, "profiles": profiles}
    try:
        with open(PROFILES_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
    except OSError as error:
        print(f"[profiles] Failed to save profiles: {error}")
    return payload


def get_active_profile() -> Optional[dict]:
    """Return the active profile dict, or None if no profiles are configured."""
    data = load_profiles()
    profiles = data.get("profiles", [])
    if not profiles:
        return None
    return profiles[data.get("active", 0)]


def format_signature(profile: Optional[dict]) -> str:
    """Render a profile into a multi-line English signature block.

    Empty fields are skipped so a partially filled profile still looks clean.
    Returns an empty string when there is nothing to sign with.
    """
    if not profile:
        return ""
    full_name = " ".join(
        part for part in (profile.get("first_name"), profile.get("last_name")) if part
    ).strip()

    lines: list[str] = []
    if full_name:
        lines.append(full_name)
    if profile.get("title"):
        lines.append(profile["title"])
    if profile.get("company"):
        lines.append(profile["company"])
    if profile.get("phone"):
        lines.append(f"Phone: {profile['phone']}")
    if profile.get("email"):
        lines.append(f"Email: {profile['email']}")
    return "\n".join(lines)


def get_active_signature() -> str:
    """Convenience: formatted signature for the currently active profile."""
    return format_signature(get_active_profile())


if __name__ == "__main__":
    # Self-test with a sample profile (not saved).
    sample = {
        "first_name": "Jordan",
        "last_name": "Rivera",
        "title": "Project Manager",
        "company": "Meridian Construction Co.",
        "phone": "+1 (555) 010-2030",
        "email": "jordan.rivera@example.com",
    }
    print("--- Sample signature ---")
    print(format_signature(sample))
