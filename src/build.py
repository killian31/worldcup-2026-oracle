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
import odds as oddslib
import predict
import simulate
import squads as squadlib
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
    """Emit each KO match with its feeder matches and bracket half, reconstructed
    even after openfootball resolves W##/L## placeholders to team names (so the
    tree never loses played matches). feeders=[] for Round-of-32."""
    by = {m["number"]: m for m in wc if m["number"] >= 73}
    winner, loser = {}, {}
    for n, m in by.items():
        if m["home_score"] is not None:
            hi = m["home_score"] >= m["away_score"]
            winner[n], loser[n] = (m["team1"], m["team2"]) if hi else (m["team2"], m["team1"])
    PREV = {"Round of 16": (range(73, 89), winner), "Quarter-final": (range(89, 97), winner),
            "Semi-final": (range(97, 101), winner), "Final": (range(101, 103), winner),
            "Match for third place": (range(101, 103), loser)}

    def feeder(name, rnd):
        if teams.is_placeholder(name):
            return int(name[1:])
        if rnd not in PREV:
            return None                      # R32 teams come from the group stage
        rng, pool = PREV[rnd]
        return next((num for num in rng if pool.get(num) == name), None)

    feeders = {n: [f for f in (feeder(m["team1"], m["round"]), feeder(m["team2"], m["round"]))
                   if f is not None] for n, m in by.items()}

    def collect(root):
        s, st = set(), [root]
        while st:
            x = st.pop(); s.add(x); st.extend(feeders.get(x, []))
        return s
    left, right = collect(101), collect(102)
    half = lambda n: "c" if n in (103, 104) else ("l" if n in left else "r")

    def slot(name):
        if teams.is_placeholder(name):
            return {"placeholder": name}
        return {"team": name, "iso": teams.iso(name),
                "champion": (odds.get(name, {}) or {}).get("champion")}
    return [{"number": n, "round": by[n]["round"], "date": by[n]["date"], "half": half(n),
             "feeders": feeders[n], "venue": (venues.info(by[n]["venue"]) or {}).get("stadium"),
             "team1": slot(by[n]["team1"]), "team2": slot(by[n]["team2"]),
             "score": ([by[n]["home_score"], by[n]["away_score"]]
                       if by[n]["home_score"] is not None else None)}
            for n in sorted(by)]


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


def _squads_payload(squads, odds):
    out = []
    for t, s in sorted(squads.items(), key=lambda kv: -kv[1]["strength"]):
        out.append({"team": t, "iso": teams.iso(t), "strength": s["strength"],
                    "n_big5": s["n_big5"], "avg_age": s["avg_age"],
                    "champion": (odds.get(t, {}) or {}).get("champion"),
                    "players": s["players"]})
    return out


def main():
    os.makedirs(DOCS, exist_ok=True)
    df, ratings = elo.attach_elo(data.load_results())
    X, y = featlib.build_features(df)
    lab = np.isfinite(y)
    dc = DixonColes().fit(df)
    gbm = gbmlib.GBM().fit(X[lab], y[lab])

    squads = squadlib.load_squads()
    preds, accuracy = predict.build_predictions(df, ratings, dc, gbm, X, squads)
    wc = data.load_wc2026()

    # merge openfootball round + venue into predictions (match on date + teams)
    rnd = {(m["date"], m["team1"], m["team2"]): (m["round"], m["venue"]) for m in wc}
    KO = {"Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Final", "Match for third place"}
    for p in preds:
        key = (p["date"], p["team1"], p["team2"])
        if key in rnd:
            p["round"] = rnd[key][0]
            p["venue"] = (venues.info(rnd[key][1]) or {}).get("stadium") or p["venue"]
        # upcoming knockouts can't end level — show a decisive projected score
        if not p["played"] and p["round"] in KO and p["pred_score"][0] == p["pred_score"][1]:
            h, a = p["pred_score"]
            p["pred_score"] = [h + 1, a] if p["probs"][0] >= p["probs"][2] else [h, a + 1]
            p["pred_outcome"] = 0 if p["pred_score"][0] > p["pred_score"][1] else 2

    # optional LIVE market-odds blend (needs ODDS_API_KEY; no-op otherwise)
    market = oddslib.fetch_market()
    for p in preds:
        mp = market.get((p["team1"], p["team2"])) if not p["played"] else None
        if mp:
            p["model_probs"] = p["probs"]
            p["market_probs"] = [round(x, 4) for x in mp]
            p["probs"] = [round(x, 4) for x in oddslib.blend(p["model_probs"], mp)]

    odds = simulate.simulate(wc, dc, ratings, n=SIMS)
    team_table = [{"team": t, "iso": teams.iso(t), "conf": teams.confederation(t),
                   "elo": round(ratings.get(t, 1500)),
                   "squad_strength": squads.get(t, {}).get("strength"),
                   "n_big5": squads.get(t, {}).get("n_big5"),
                   "avg_age": squads.get(t, {}).get("avg_age"), **o}
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
        "live_odds": any("market_probs" in p for p in preds),
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
    dump(_squads_payload(squads, odds), "squads.json")
    dump(meta, "meta.json")
    print(f"build OK — {len(played)} played, {len(upcoming)} upcoming, "
          f"RPS {accuracy.get('rps')}, champion fav "
          f"{team_table[0]['team']} {team_table[0]['champion']*100:.1f}%")


if __name__ == "__main__":
    main()
