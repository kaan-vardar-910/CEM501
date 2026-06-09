"""Contact book with importance-based triage overrides (BONUS).

Stores known correspondents in a JSON file. Senders are auto-captured when the
inbox is read, and the user can add or classify contacts by importance:

    normal  -> no effect on triage
    vip     -> elevate the email to at least ACTION
    urgent  -> always classify the email as URGENT

The reader consults these classifications so that "important" people always
surface at the top of the triage, regardless of the subject line wording.
"""

from __future__ import annotations

import json
import os
from typing import Optional

CONTACTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "contacts.json"
)

# Allowed importance levels, lowest to highest triage influence.
IMPORTANCE_LEVELS = ("normal", "vip", "urgent")


def _default_contacts() -> dict:
    """Return the empty contacts structure."""
    return {"contacts": []}


def _normalize_email(value: object) -> str:
    """Lower-case and trim an email address for stable comparisons."""
    return str(value).strip().lower() if value is not None else ""


def _clean_contact(raw: object) -> Optional[dict]:
    """Validate/coerce a raw contact dict; return None if it has no email.

    Carries the contact-book fields used by the document sender (``role`` and
    ``cc_always``) alongside the triage ``importance`` so a single contact store
    serves both features.
    """
    if not isinstance(raw, dict):
        return None
    email = _normalize_email(raw.get("email"))
    if not email:
        return None
    importance = str(raw.get("importance", "normal")).strip().lower()
    if importance not in IMPORTANCE_LEVELS:
        importance = "normal"
    return {
        "name": str(raw.get("name", "")).strip(),
        "email": email,
        "role": str(raw.get("role", "")).strip(),
        "importance": importance,
        "cc_always": bool(raw.get("cc_always", False)),
    }


def load_contacts() -> dict:
    """Load contacts.json, returning the empty structure on any error."""
    if not os.path.exists(CONTACTS_PATH):
        return _default_contacts()
    try:
        with open(CONTACTS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as error:
        print(f"[contacts] Could not read contacts: {error}")
        return _default_contacts()

    contacts = []
    seen: set[str] = set()
    for raw in data.get("contacts", []):
        clean = _clean_contact(raw)
        if clean and clean["email"] not in seen:
            contacts.append(clean)
            seen.add(clean["email"])
    return {"contacts": contacts}


def save_contacts(data: dict) -> dict:
    """Persist a full contacts structure (de-duplicated) and return it."""
    contacts = []
    seen: set[str] = set()
    for raw in data.get("contacts", []):
        clean = _clean_contact(raw)
        if clean and clean["email"] not in seen:
            contacts.append(clean)
            seen.add(clean["email"])
    payload = {"contacts": contacts}
    try:
        with open(CONTACTS_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
    except OSError as error:
        print(f"[contacts] Failed to save contacts: {error}")
    return payload


def get_importance(email: str) -> str:
    """Return the importance level for an email ('normal' if unknown)."""
    target = _normalize_email(email)
    for contact in load_contacts()["contacts"]:
        if contact["email"] == target:
            return contact["importance"]
    return "normal"


def get_contacts() -> list[dict]:
    """Return the full contact list (empty list if none are configured)."""
    return load_contacts().get("contacts", [])


def add_contact(
    name: str,
    email: str,
    role: str,
    cc_always: bool = False,
    importance: str = "normal",
) -> None:
    """Append (or update) a single contact and persist the change.

    If a contact with the same email already exists, its fields are updated in
    place rather than duplicated.
    """
    key = _normalize_email(email)
    if not key:
        raise ValueError("A contact requires an email address.")
    data = load_contacts()
    by_email = {c["email"]: c for c in data["contacts"]}
    by_email[key] = {
        "name": str(name).strip(),
        "email": key,
        "role": str(role).strip(),
        "importance": str(importance).strip().lower(),
        "cc_always": bool(cc_always),
    }
    save_contacts({"contacts": list(by_email.values())})


def get_cc_always_contacts() -> list[str]:
    """Return the email addresses of every contact flagged ``cc_always``."""
    return [
        contact["email"]
        for contact in load_contacts()["contacts"]
        if contact.get("cc_always")
    ]


def bulk_upsert_senders(senders: list[tuple[str, str]]) -> dict:
    """Add any unseen senders as 'normal' contacts; keep existing ones intact.

    ``senders`` is a list of (display_name, email) tuples. Existing contacts
    keep their importance and (if already set) their name. Returns the updated
    contacts structure. Writes the file once for the whole batch.
    """
    data = load_contacts()
    by_email = {c["email"]: c for c in data["contacts"]}
    changed = False
    for name, email in senders:
        key = _normalize_email(email)
        if not key:
            continue
        if key not in by_email:
            by_email[key] = {
                "name": str(name).strip(),
                "email": key,
                "importance": "normal",
            }
            changed = True
        elif not by_email[key]["name"] and str(name).strip():
            # Backfill a missing display name without touching the importance.
            by_email[key]["name"] = str(name).strip()
            changed = True

    if changed:
        return save_contacts({"contacts": list(by_email.values())})
    return data


if __name__ == "__main__":
    # Self-test (writes to contacts.json in this folder).
    bulk_upsert_senders([("Test Sender", "test.sender@example.com")])
    print("Contacts after upsert:")
    print(json.dumps(load_contacts(), indent=2))
    print("Importance of test.sender@example.com:",
          get_importance("test.sender@example.com"))
