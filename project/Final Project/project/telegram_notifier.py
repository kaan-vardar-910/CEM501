"""Telegram alert integration (BONUS — Week 11 multi-channel).

Pushes URGENT email alerts and the morning digest to a Telegram chat using
only the requests library. Every function is defensive: a missing token or a
network failure produces a warning and a False return value, never an
exception, so the main agent pipeline is never interrupted by a side channel.
"""

from __future__ import annotations

import os
from datetime import datetime

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Telegram caps a single message at 4096 characters.
TELEGRAM_MAX_CHARS = 4096
TELEGRAM_API_BASE = "https://api.telegram.org"


def _send_message(text: str) -> bool:
    """Post a plain-text message to the configured Telegram chat.

    Shared by the alert and digest helpers. Returns True only on a confirmed
    2xx response; any missing-config or network problem returns False after
    printing a warning.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print(
            "[telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set; "
            "skipping Telegram notification."
        )
        return False

    try:
        import requests
    except ImportError:
        print("[telegram] The 'requests' package is not installed; skipping.")
        return False

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:TELEGRAM_MAX_CHARS]}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            return True
        print(
            f"[telegram] API returned status {response.status_code}: "
            f"{response.text[:200]}"
        )
        return False
    except Exception as error:  # noqa: BLE001 - network errors must not crash.
        print(f"[telegram] Network error sending message: {error}")
        return False


def send_telegram_alert(subject: str, sender: str, preview: str) -> bool:
    """Send a formatted URGENT-email alert to Telegram.

    Returns True on success, False if Telegram is not configured or the
    request fails. Safe to call unconditionally for every urgent email.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = (
        "URGENT PROJECT ALERT\n"
        "--------------------\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n"
        f"Preview: {preview[:100]}\n"
        "--------------------\n"
        f"{timestamp}"
    )
    return _send_message(message)


def send_telegram_digest(digest_text: str) -> bool:
    """Send the morning digest to Telegram, truncated to the 4096-char limit.

    Returns True on success, False otherwise.
    """
    return _send_message(digest_text[:TELEGRAM_MAX_CHARS])


if __name__ == "__main__":
    # Exercises the alert path; prints a graceful warning if no token is set.
    print("Sending a test Telegram alert (requires TELEGRAM_BOT_TOKEN)...")
    ok = send_telegram_alert(
        subject="Fall protection deficiency — immediate correction required",
        sender="Safety Inspector <inspector@example.com>",
        preview="A fall protection deficiency was observed on the east edge.",
    )
    print(f"Alert sent: {ok}")
