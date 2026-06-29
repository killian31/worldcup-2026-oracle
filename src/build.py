"""Pipeline orchestrator: fetch -> Elo -> features -> fit -> predict -> simulate
-> write docs/data/*.json for the static site. Runs in CI on a schedule; reuses
the committed benchmark.json (the slow walk-forward is run on demand).
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

import data
import elo
import features as featlib
import gbm as gbmlib
import predict
import simulate
import teams
import venues
from model import DixonColes

DOCS = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
SIMS = int(os.environ.get("WC_SIMS", "50000"))


def _coerce(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def dump(obj, name):
    json.dump(obj, open(os.path.join(DOCS, name), "w"), indent=2, default=_coerce)


def _standings(wc):
    groups = {}
    for m in wc:
        g = m.get("group")
        if not g or m["home_score"] is None:
            continue
        t = groups.setdefault(g, {})
        for team, gf, ga in ((m["team1"], m["home_score"], m["away_score"]),
                             (m["team2"], m["away_score"], m["home_score"])):
            r = t.setdefault(team, {"team": team, "iso": teams.iso(team), "P": 0,
                                    "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0})
            r["P"] += 1; r["GF"] += gf; r["GA"] += ga
            r["W"] += gf > ga; r["D"] += gf == ga; r["L"] += gf < ga
            r["Pts"] += 3 if gf > ga else (1 if gf == ga else 0)
    out = {}
    for g, t in sorted(groups.items()):
        rows = sorted(t.values(), key=lambda r: (-r["Pts"], -(r["GF"] - r["GA"]), -r["GF"]))
        for r in rows:
            r["GD"] = r["GF"] - r["GA"]
        out[g] = rows
    return out


def _bracket(wc, odds):
    ko = [m for m in wc if m["number"] >= 73]
    out = []
    for m in sorted(ko, key=lambda m: m["number"]):
        def slot(name):
            if teams.is_placeholder(name):
                return {"placeholder": name}
            return {"team": name, "iso": teams.iso(name),
                    "champion": (odds.get(name, {}) or {}).get("champion")}
        out.append({"number": m["number"], "round": m["round"], "date": m["date"],
                    "venue": (venues.info(m["venue"]) or {}).get("stadium"),
                    "team1": slot(m["team1"]), "team2": slot(m["team2"]),
                    "score": ([m["home_score"], m["away_score"]]
                              if m["home_score"] is not None else None)})
    return out


def _history(df):
    """Champion of each past men's World Cup (winner of that edition's final)."""
    wc = df[(df.tournament == "FIFA World Cup") & df.played]
    out = []
    for yr, g in wc.groupby(df["date"].dt.year):
        if yr >= 2026:
            continue
        final = g.sort_values("date").iloc[-1]
        champ = final.home_team if final.home_score >= final.away_score else final.away_team
        out.append({"year": int(yr), "champion": champ, "iso": teams.iso(champ)})
    return sorted(out, key=lambda r: -r["year"])


def main():
    os.makedirs(DOCS, exist_ok=True)
    df, ratings = elo.attach_elo(data.load_results())
    X, y = featlib.build_features(df)
    lab = np.isfinite(y)
    dc = DixonColes().fit(df)
    gbm = gbmlib.GBM().fit(X[lab], y[lab])

    preds, accuracy = predict.build_predictions(df, ratings, dc, gbm, X)
    wc = data.load_wc2026()

    # merge openfootball round + venue into predictions (match on date + teams)
    rnd = {(m["date"], m["team1"], m["team2"]): (m["round"], m["venue"]) for m in wc}
    for p in preds:
        key = (p["date"], p["team1"], p["team2"])
        if key in rnd:
            p["round"] = rnd[key][0]
            p["venue"] = (venues.info(rnd[key][1]) or {}).get("stadium") or p["venue"]

    odds = simulate.simulate(wc, dc, ratings, n=SIMS)
    team_table = [{"team": t, "iso": teams.iso(t), "conf": teams.confederation(t),
                   "elo": round(ratings.get(t, 1500)), **o}
                  for t, o in odds.items()]

    played = [p for p in preds if p["played"]]
    results = sorted(played, key=lambda p: p["date"], reverse=True)[:40]

    now = dt.datetime.now(dt.UTC).replace(microsecond=0, tzinfo=None)
    upcoming = [p for p in preds if not p["played"]]
    meta = {
        "updated_utc": now.isoformat() + "Z",
        "tournament": "FIFA World Cup 2026",
        "matches_total": 104, "matches_played": len(played),
        "matches_upcoming_known": len(upcoming),
        "model": "Elo -> Dixon-Coles + HistGBM ensemble (calibrated)",
        "sims": SIMS,
        "accuracy_rps": accuracy.get("rps"), "accuracy_pct": accuracy.get("accuracy"),
        "sources": ["martj42/international_results (CC0)",
                    "openfootball/worldcup.json (CC0)", "Open-Meteo (weather)"],
        "note": "Free-tier data; in-play scores may be delayed.",
    }

    dump(preds, "predictions.json")
    dump(accuracy, "accuracy.json")
    dump(team_table, "championship.json")
    dump(_bracket(wc, odds), "bracket.json")
    dump(_standings(wc), "standings.json")
    dump(results, "results.json")
    dump(_history(df), "history.json")
    dump(meta, "meta.json")
    print(f"build OK — {len(played)} played, {len(upcoming)} upcoming, "
          f"RPS {accuracy.get('rps')}, champion fav "
          f"{team_table[0]['team']} {team_table[0]['champion']*100:.1f}%")


if __name__ == "__main__":
    main()
