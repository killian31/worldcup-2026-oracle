"""Load + cache the two no-key data sources.

- martj42/international_results : full match history (training corpus) AND the
  2026 results as they are played.  Canonical team names.
- openfootball/worldcup.json   : the 2026 bracket *tree* (W##/L## advancement)
  which martj42 does not encode.

Both are public-domain and need no API key, so the whole pipeline runs with zero
secrets. football-data.org is layered on optionally elsewhere for live status.
"""
import json
import os
import time
import urllib.request

import pandas as pd

import teams

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
SHOOTOUTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"
OPENFOOTBALL_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

# FIFA match-number ranges per knockout round (group = 1..72 in file order)
_KO_START = {"Round of 32": 73, "Round of 16": 89, "Quarter-final": 97,
             "Semi-final": 101, "Match for third place": 103, "Final": 104}


def _download(url, name, max_age_hours=6):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_hours * 3600
    if not fresh:
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as e:  # keep stale cache rather than crash a scheduled run
            if not os.path.exists(path):
                raise
            print(f"warn: refresh of {name} failed ({e}); using cached copy")
    return path


def load_results(max_age_hours=6):
    """All international results, cleaned. `played` flags rows with a final score."""
    df = pd.read_csv(_download(RESULTS_URL, "results.csv", max_age_hours))
    df["date"] = pd.to_datetime(df["date"])
    df["home_team"] = df["home_team"].map(teams.normalize)
    df["away_team"] = df["away_team"].map(teams.normalize)
    df["neutral"] = df["neutral"].astype(str).str.upper().eq("TRUE")
    for c in ("home_score", "away_score"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["played"] = df["home_score"].notna() & df["away_score"].notna()
    return df.sort_values("date").reset_index(drop=True)


def load_wc2026(max_age_hours=6):
    """2026 matches with FIFA match numbers, venue ids, and bracket placeholders.

    Returns a list of dicts: number, round, date, team1, team2 (canonical name or
    'W##'/'L##'), venue (id), ground (raw). Group matches keep concrete teams.
    """
    import venues
    path = _download(OPENFOOTBALL_URL, "worldcup2026.json", max_age_hours)
    raw = json.load(open(path, encoding="utf-8"))["matches"]
    out, group_n = [], 0
    ko_counter = {k: 0 for k in _KO_START}
    for m in raw:
        rnd = m.get("round", "")
        if rnd in _KO_START:
            number = _KO_START[rnd] + ko_counter[rnd]
            ko_counter[rnd] += 1
        else:
            group_n += 1
            number = group_n
        ground = m.get("ground", "")
        sc = m.get("score", {}) or {}
        ft = sc.get("ft")
        out.append({
            "number": number,
            "round": rnd,
            "date": m.get("date"),
            "time": m.get("time"),
            "team1": teams.normalize(m.get("team1")),
            "team2": teams.normalize(m.get("team2")),
            "venue": venues.resolve(ground),
            "ground": ground,
            "group": m.get("group"),
            "home_score": ft[0] if ft else None,
            "away_score": ft[1] if ft else None,
        })
    # validate the bracket tree: every W##/L## points at a real match number
    nums = {m["number"] for m in out}
    for m in out:
        for slot in ("team1", "team2"):
            v = m[slot]
            if teams.is_placeholder(v):
                assert int(v[1:]) in nums, f"dangling ref {v} in match {m['number']}"
    return out


if __name__ == "__main__":
    df = load_results()
    print(f"results: {len(df):,} matches {df.date.min().date()}..{df.date.max().date()}")
    wc = load_wc2026()
    played = sum(1 for m in wc if m["home_score"] is not None)
    print(f"wc2026: {len(wc)} matches, {played} played")
    unresolved = [m["venue"] is None for m in wc]
    assert not any(unresolved), "some venues failed to resolve"
    print("all venues resolved OK")
