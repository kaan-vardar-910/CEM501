"""City -> coordinate lookup for Daily Report project-location selection.

A small curated list (major Turkish provinces plus a few international cities)
with accurate decimal-degree coordinates. Used to populate the Settings city
dropdown so selecting a city auto-fills the site latitude/longitude that drives
auto-weather, without needing an external geocoding call.
"""

from __future__ import annotations

# name -> (latitude, longitude)
CITIES: dict[str, tuple[float, float]] = {
    # --- Turkey (major provinces) ---
    "İstanbul": (41.0082, 28.9784),
    "Ankara": (39.9334, 32.8597),
    "İzmir": (38.4237, 27.1428),
    "Bursa": (40.1885, 29.0610),
    "Antalya": (36.8969, 30.7133),
    "Adana": (37.0000, 35.3213),
    "Konya": (37.8746, 32.4932),
    "Gaziantep": (37.0662, 37.3833),
    "Kayseri": (38.7312, 35.4787),
    "Mersin": (36.8121, 34.6415),
    "Eskişehir": (39.7767, 30.5206),
    "Diyarbakır": (37.9144, 40.2306),
    "Samsun": (41.2867, 36.3300),
    "Denizli": (37.7765, 29.0864),
    "Trabzon": (41.0015, 39.7178),
    "Erzurum": (39.9000, 41.2700),
    "Malatya": (38.3552, 38.3095),
    "Van": (38.4942, 43.3800),
    "Şanlıurfa": (37.1591, 38.7969),
    "Kocaeli": (40.7654, 29.9408),
    "Sakarya": (40.7869, 30.4036),
    "Hatay": (36.2025, 36.1606),
    "Manisa": (38.6191, 27.4289),
    "Balıkesir": (39.6484, 27.8826),
    "Aydın": (37.8444, 27.8458),
    "Muğla": (37.2153, 28.3636),
    "Tekirdağ": (40.9780, 27.5117),
    "Çanakkale": (40.1553, 26.4142),
    "Bolu": (40.5760, 31.5788),
    "Zonguldak": (41.4564, 31.7987),
    "Kütahya": (39.4242, 29.9833),
    "Afyonkarahisar": (38.7507, 30.5567),
    "Sivas": (39.7477, 37.0179),
    "Elazığ": (38.6810, 39.2264),
    "Ordu": (40.9839, 37.8764),
    "Erzincan": (39.7500, 39.5000),
    "Tokat": (40.3167, 36.5500),
    "Kahramanmaraş": (37.5858, 36.9371),
    "Mardin": (37.3212, 40.7245),
    "Isparta": (37.7648, 30.5566),
    # --- International ---
    "London": (51.5074, -0.1278),
    "Paris": (48.8566, 2.3522),
    "Berlin": (52.5200, 13.4050),
    "New York": (40.7128, -74.0060),
    "Dubai": (25.2048, 55.2708),
    "Tokyo": (35.6762, 139.6503),
}


def list_cities() -> list[dict]:
    """Return cities as a sorted list of ``{name, lat, lng}`` dicts."""
    return [
        {"name": name, "lat": lat, "lng": lng}
        for name, (lat, lng) in CITIES.items()
    ]


def get_coordinates(city: str) -> tuple[float, float] | None:
    """Return ``(lat, lng)`` for ``city`` (exact match) or None."""
    return CITIES.get(city)


if __name__ == "__main__":
    print(f"{len(CITIES)} cities available.")
    print("İstanbul ->", get_coordinates("İstanbul"))
