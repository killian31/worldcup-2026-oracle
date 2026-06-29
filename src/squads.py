"""Squad / player layer (free, zero-secret).

openfootball's 2026 squad file gives 26 players per team with club + club-country
+ DOB. We rate each player by the strength of the league their CLUB plays in
(a robust, dependency-free proxy for player quality — a squad full of big-5-league
players is strong), and aggregate to a squad-strength index. This is a CURRENT-
squad expert overlay, not a back-testable feature (historical squads aren't free),
so it informs display, explainability, and a small bounded prediction tilt — never
the walk-forward benchmark.
"""
import datetime as dt
import json
import os

import teams

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "squads.json")
SQUADS_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.squads.json"

# club-league strength by openfootball 3-letter club-country code (0-100).
LEAGUE = {
    "ENG": 100, "ESP": 96, "ITA": 90, "GER": 90, "FRA": 85, "POR": 78, "NED": 76,
    "BRA": 74, "ARG": 68, "BEL": 70, "TUR": 66, "KSA": 66, "USA": 60, "MEX": 60,
    "GRE": 60, "SUI": 60, "RUS": 60, "SCO": 58, "AUT": 58, "DEN": 58, "JPN": 58,
    "UKR": 56, "CRO": 56, "CZE": 56, "SRB": 56, "COL": 56, "URU": 56, "NOR": 54,
    "SWE": 54, "POL": 54, "KOR": 54, "QAT": 54, "ECU": 54, "CHI": 54, "UAE": 52,
    "PAR": 52, "EGY": 50, "MAR": 50, "IRN": 50, "AUS": 50, "CAN": 48, "UZB": 46,
    "RSA": 46, "IRQ": 44, "JOR": 44, "NZL": 40,
}
DEFAULT_LEAGUE = 45
BIG5 = {"ENG", "ESP", "ITA", "GER", "FRA"}


def _download(max_age_hours=24):
    import urllib.request
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    import time
    fresh = os.path.exists(CACHE) and (time.time() - os.path.getmtime(CACHE)) < max_age_hours * 3600
    if not fresh:
        try:
            urllib.request.urlretrieve(SQUADS_URL, CACHE)
        except Exception as e:
            if not os.path.exists(CACHE):
                raise
            print(f"warn: squad refresh failed ({e}); using cache")
    return CACHE


def _age(dob, today):
    try:
        y, m, d = map(int, dob.split("-"))
        return round((today - dt.date(y, m, d)).days / 365.25, 1)
    except Exception:
        return None


def load_squads(max_age_hours=24):
    """team (canonical) -> {players[], strength, n_big5, avg_age, top_clubs}."""
    raw = json.load(open(_download(max_age_hours), encoding="utf-8"))
    today = dt.date.today()
    out = {}
    for tm in raw:
        name = teams.normalize(tm["name"])
        players = []
        for p in tm.get("players", []):
            club = p.get("club") or {}
            cc = club.get("country") if isinstance(club, dict) else None
            players.append({
                "name": p.get("name"), "pos": p.get("pos"),
                "club": club.get("name") if isinstance(club, dict) else club,
                "club_country": cc, "league": LEAGUE.get(cc, DEFAULT_LEAGUE),
                "age": _age(p.get("date_of_birth", ""), today),
            })
        if not players:
            continue
        ranked = sorted(players, key=lambda x: -x["league"])
        top = ranked[:15]                       # proxy first-team quality
        top15 = sum(x["league"] for x in top) / len(top)
        n_big5 = sum(1 for x in players if x["club_country"] in BIG5)
        # blend league quality with big-5 depth so saturation at the top still
        # separates an elite-laden squad from a merely big-5-present one
        strength = 0.8 * top15 + 0.2 * (n_big5 / 26 * 100)
        ages = [x["age"] for x in players if x["age"]]
        out[name] = {
            "players": players,
            "strength": round(strength, 1),
            "n_big5": n_big5,
            "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
            "top_clubs": list(dict.fromkeys(x["club"] for x in ranked[:5])),
        }
    return out


if __name__ == "__main__":
    import numpy as np
    import data, elo
    sq = load_squads()
    print(f"loaded {len(sq)} squads, {sum(len(s['players']) for s in sq.values())} players")
    top = sorted(sq.items(), key=lambda kv: -kv[1]["strength"])[:8]
    for t, s in top:
        print(f"  {s['strength']:5.1f}  big5 {s['n_big5']:2d}/26  age {s['avg_age']}  {t}")
    # how much does squad strength overlap with Elo? (decides if it adds info)
    _, ratings = elo.attach_elo(data.load_results())
    common = [t for t in sq if t in ratings]
    e = np.array([ratings[t] for t in common]); s = np.array([sq[t]["strength"] for t in common])
    print(f"\ncorr(squad_strength, Elo) over {len(common)} teams = {np.corrcoef(e, s)[0,1]:.2f}")
    assert len(sq) == 48
    print("squads OK")
