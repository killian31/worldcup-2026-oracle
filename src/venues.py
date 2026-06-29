"""WC2026 host venues: coordinates, elevation, timezone offset, and resolution
from the free-text city/ground strings used by martj42 and openfootball.

Only 2 of 16 venues are high-altitude (Mexico City ~2200 m, Guadalajara ~1566 m);
that is where the altitude-gap feature has leverage. UTC offsets are the June/July
2026 values (Mexico has no DST; US/CA on daylight time).
"""
from math import radians, sin, cos, asin, sqrt

# id: (stadium, country, lat, lon, elevation_m, utc_offset_hours, iana_tz)
VENUES = {
    "mexico_city":  ("Estadio Azteca",        "Mexico",  19.3030,  -99.1505, 2200, -6, "America/Mexico_City"),
    "guadalajara":  ("Estadio Akron",         "Mexico",  20.6819, -103.4626, 1566, -6, "America/Mexico_City"),
    "monterrey":    ("Estadio BBVA",          "Mexico",  25.6692, -100.2444,  540, -6, "America/Monterrey"),
    "atlanta":      ("Mercedes-Benz Stadium", "USA",     33.7554,  -84.4008,  320, -4, "America/New_York"),
    "kansas_city":  ("Arrowhead Stadium",     "USA",     39.0489,  -94.4839,  270, -5, "America/Chicago"),
    "dallas":       ("AT&T Stadium",          "USA",     32.7473,  -97.0945,  180, -5, "America/Chicago"),
    "toronto":      ("BMO Field",             "Canada",  43.6332,  -79.4185,   76, -4, "America/Toronto"),
    "boston":       ("Gillette Stadium",      "USA",     42.0909,  -71.2643,   70, -4, "America/New_York"),
    "seattle":      ("Lumen Field",           "USA",     47.5952, -122.3316,   50, -7, "America/Los_Angeles"),
    "los_angeles":  ("SoFi Stadium",          "USA",     33.9535, -118.3392,   30, -7, "America/Los_Angeles"),
    "houston":      ("NRG Stadium",           "USA",     29.6847,  -95.4107,   15, -5, "America/Chicago"),
    "philadelphia": ("Lincoln Financial Field","USA",    39.9008,  -75.1675,   12, -4, "America/New_York"),
    "new_york":     ("MetLife Stadium",       "USA",     40.8135,  -74.0745,    5, -4, "America/New_York"),
    "san_francisco":("Levi's Stadium",        "USA",     37.4030, -121.9700,    5, -7, "America/Los_Angeles"),
    "miami":        ("Hard Rock Stadium",     "USA",     25.9580,  -80.2389,    3, -4, "America/New_York"),
    "vancouver":    ("BC Place",              "Canada",  49.2768, -123.1119,    3, -7, "America/Vancouver"),
}

# distinctive token -> venue id (matched case-insensitively against city/ground text)
_TOKENS = {
    "mexico city": "mexico_city", "azteca": "mexico_city",
    "guadalajara": "guadalajara", "akron": "guadalajara", "zapopan": "guadalajara",
    "monterrey": "monterrey", "guadalupe": "monterrey", "bbva": "monterrey",
    "atlanta": "atlanta",
    "kansas": "kansas_city",
    "dallas": "dallas", "arlington": "dallas",
    "toronto": "toronto",
    "boston": "boston", "foxboro": "boston", "foxborough": "boston", "gillette": "boston",
    "seattle": "seattle",
    "los angeles": "los_angeles", "inglewood": "los_angeles", "sofi": "los_angeles",
    "houston": "houston",
    "philadelphia": "philadelphia",
    "new york": "new_york", "east rutherford": "new_york", "metlife": "new_york",
    "san francisco": "san_francisco", "santa clara": "san_francisco", "levi": "san_francisco",
    "miami": "miami",
    "vancouver": "vancouver",
}


# Principal home-venue elevation (m) by country — only the high-altitude ones
# matter (the rest default to ~50 m). Used both for the match venue (historical,
# keyed by host country) and for a team's home base (team name == country).
COUNTRY_ELEVATION = {
    "Bolivia": 3640, "Ecuador": 2850, "Colombia": 2640, "Mexico": 2240,
    "Ethiopia": 2355, "Afghanistan": 1790, "Kenya": 1795, "South Africa": 1400,
    "Lesotho": 1600, "Rwanda": 1567, "Guatemala": 1500, "Zimbabwe": 1490,
    "Iran": 1200, "Zambia": 1280, "Armenia": 1000, "Spain": 667, "Saudi Arabia": 600,
    "Switzerland": 400, "Turkey": 850, "Austria": 170, "Peru": 150,
}


def country_elev(country):
    return COUNTRY_ELEVATION.get(country, 50)


def venue_elev_for_match(venue_id, country):
    """Precise venue elevation for 2026 matches; country fallback for history."""
    if venue_id and venue_id in VENUES:
        return VENUES[venue_id][4]
    return country_elev(country)


def resolve(text):
    """Map a free-text city or ground string to a venue id, or None."""
    if not text:
        return None
    t = text.lower()
    for token, vid in _TOKENS.items():
        if token in t:
            return vid
    return None


def info(vid):
    v = VENUES.get(vid)
    if not v:
        return None
    keys = ("stadium", "country", "lat", "lon", "elev", "utc_offset", "tz")
    return dict(zip(keys, v))


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


if __name__ == "__main__":
    # self-check: every venue resolves from its own city token; distances sane
    assert resolve("Mexico City") == "mexico_city"
    assert resolve("New York/New Jersey (East Rutherford)") == "new_york"
    assert resolve("Guadalupe") == "monterrey"
    assert resolve("nowhere") is None
    d = haversine_km(*[VENUES["los_angeles"][i] for i in (2, 3)],
                     *[VENUES["new_york"][i] for i in (2, 3)])
    assert 3800 < d < 4200, d  # LA-NY ~3940 km
    print("venues OK — 16 venues,", f"LA-NY {d:.0f} km")
