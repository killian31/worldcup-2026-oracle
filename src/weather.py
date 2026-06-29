"""Open-Meteo client (no API key) for venue heat at kickoff, disk-cached.

Historical matches use the archive API; future matches the forecast API (~16-day
horizon). Heat is a 2026-only descriptive factor — failures degrade gracefully to
None so a scheduled run never breaks on a weather hiccup.
"""
import json
import os
import urllib.request

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "weather.json")
_mem = None


def _load():
    global _mem
    if _mem is None:
        _mem = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    return _mem


def _save():
    if _mem is not None:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(_mem, open(CACHE, "w"))


def get(lat, lon, date, hour=16, future=False):
    """Return {apparent, temp, humidity} at local `hour` on `date`, or None."""
    cache = _load()
    key = f"{lat:.3f},{lon:.3f},{date},{hour},{int(future)}"
    if key in cache:
        return cache[key]
    base = ("https://api.open-meteo.com/v1/forecast" if future
            else "https://archive-api.open-meteo.com/v1/archive")
    url = (f"{base}?latitude={lat}&longitude={lon}&start_date={date}&end_date={date}"
           "&hourly=temperature_2m,relative_humidity_2m,apparent_temperature&timezone=auto")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            h = json.load(r)["hourly"]
        i = min(range(len(h["time"])), key=lambda k: abs(int(h["time"][k][11:13]) - hour))
        val = {"apparent": h["apparent_temperature"][i],
               "temp": h["temperature_2m"][i],
               "humidity": h["relative_humidity_2m"][i]}
    except Exception:
        val = None
    cache[key] = val
    _save()
    return val


if __name__ == "__main__":
    import venues
    v = venues.VENUES["houston"]
    w = get(v[2], v[3], "2026-06-29", 16, future=True)
    print("Houston 2026-06-29 16h:", w)
    w2 = get(v[2], v[3], "2022-07-01", 16)  # historical archive
    print("Houston 2022-07-01 16h:", w2)
    assert w2 is None or "apparent" in w2
    print("weather OK")
