"""Lightweight site-weather helper for the daily report module.

Uses the free, key-less Open-Meteo API to fetch a short morning/afternoon
weather summary for a site's latitude/longitude. The location is read from the
``SITE_LAT`` / ``SITE_LNG`` environment variables (set them in ``.env``). All
network and parsing errors degrade gracefully so a missing location or an
offline run never breaks report creation.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Corporate/Windows TLS interception can break Python's bundled CA store; make
# Python trust the OS certificate store (same fix used in templates.py).
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import requests

# Minimal WMO weather-code descriptions (Open-Meteo ``weathercode``).
_WMO = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}


def get_site_location() -> Optional[tuple[float, float]]:
    """Return (lat, lng) from SITE_LAT/SITE_LNG env vars, or None if unset."""
    lat = os.getenv("SITE_LAT")
    lng = os.getenv("SITE_LNG")
    if not lat or not lng:
        return None
    try:
        return float(lat), float(lng)
    except ValueError:
        return None


def _summarise(codes: list[int], temps: list[float], precip: list[float]) -> str:
    """Build a one-line summary from a window's hourly samples."""
    if not temps:
        return ""
    code = max(set(codes), key=codes.count) if codes else 0
    desc = _WMO.get(code, "Mixed conditions")
    avg_temp = round(sum(temps) / len(temps))
    total_precip = round(sum(precip), 1)
    rain = f", {total_precip} mm precip" if total_precip > 0 else ""
    return f"{desc}, {avg_temp}\u00b0C{rain}"


def get_weather(lat: float, lng: float) -> dict:
    """Fetch a morning/afternoon weather summary for ``lat``/``lng``.

    Returns ``{"ok": True, "morning": str, "afternoon": str}`` on success or
    ``{"ok": False, "error": str}`` on any failure.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lng,
        "hourly": "temperature_2m,precipitation,weathercode",
        "forecast_days": 1,
        "timezone": "auto",
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        hourly = response.json().get("hourly", {})
    except (requests.RequestException, ValueError) as error:
        return {"ok": False, "error": f"Weather fetch failed: {error}"}

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precip = hourly.get("precipitation", [])
    codes = hourly.get("weathercode", [])
    if not times:
        return {"ok": False, "error": "No weather data returned."}

    morning = {"t": [], "p": [], "c": []}
    afternoon = {"t": [], "p": [], "c": []}
    for i, stamp in enumerate(times):
        try:
            hour = int(stamp[11:13])
        except (ValueError, IndexError):
            continue
        bucket = None
        if 6 <= hour < 12:
            bucket = morning
        elif 12 <= hour < 18:
            bucket = afternoon
        if bucket is None:
            continue
        if i < len(temps):
            bucket["t"].append(temps[i])
        if i < len(precip):
            bucket["p"].append(precip[i])
        if i < len(codes):
            bucket["c"].append(codes[i])

    return {
        "ok": True,
        "morning": _summarise(morning["c"], morning["t"], morning["p"]),
        "afternoon": _summarise(afternoon["c"], afternoon["t"], afternoon["p"]),
    }


def get_site_weather() -> dict:
    """Fetch weather for the configured site location.

    Returns ``{"ok": False, "configured": False, ...}`` when no location is set
    so the UI can prompt the user to configure SITE_LAT/SITE_LNG.
    """
    location = get_site_location()
    if not location:
        return {
            "ok": False,
            "configured": False,
            "error": "Set SITE_LAT and SITE_LNG in .env for auto weather.",
        }
    result = get_weather(*location)
    result["configured"] = True
    return result


if __name__ == "__main__":
    print("Site location:", get_site_location())
    # Sample coordinates (Istanbul) for a self-test if no env location is set.
    demo = get_site_location() or (41.0082, 28.9784)
    print("Weather for", demo)
    print(get_weather(*demo))
