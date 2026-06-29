"""2026 World Cup match predictions + accuracy backfill.

For every 2026 match present in martj42 (group + resolved knockouts) we produce
the ensemble (Dixon-Coles + GBM) 1X2 probabilities and a predicted scoreline,
using each match's PRE-match Elo/features (leakage-safe), so played matches give
an honest "accuracy so far". Descriptive "why" factors (altitude, heat, rest,
quasi-home crowd) annotate each card; a small, explicit diaspora tilt is the only
factor that nudges the published probability.
"""
import datetime as dt

import numpy as np

import features as featlib
import gbm as gbmlib
import metrics
import teams
import venues
import weather
from model import DixonColes, coherent_score, decisive_score, score_outcome

HOST_COUNTRIES = {"United States", "Mexico", "Canada"}


def _parse_hour(t):
    try:
        return int(str(t).split(":")[0].strip()[-2:])
    except Exception:
        return 16


def _logit_tilt(probs, tilt):
    """Shift home-vs-away by `tilt` (logit), keep draw, renormalise."""
    h, d, a = probs
    h, a = h * np.exp(tilt / 2), a * np.exp(-tilt / 2)
    s = h + d + a
    return [h / s, d / s, a / s]


def _factors(row, x, wx, t1, t2, venue_id, country):
    """Return (factor list, diaspora tilt toward home)."""
    out, tilt = [], 0.0
    # altitude (already in the model via alt_gap; surfaced for context)
    if x["alt_gap_away"] > x["alt_gap_home"] + 0.5:
        out.append({"icon": "⛰️", "text": f"Altitude edge: {t1} (opponent {int(x['alt_gap_away']*1000)} m above home base)", "favors": "home"})
    elif x["alt_gap_home"] > x["alt_gap_away"] + 0.5:
        out.append({"icon": "⛰️", "text": f"Altitude edge: {t2}", "favors": "away"})
    # heat
    if wx and wx.get("apparent") is not None and wx["apparent"] >= 30:
        out.append({"icon": "🔥", "text": f"Heat {wx['apparent']:.0f}°C apparent — suppresses pressing, lowers tempo", "favors": "none"})
    # quasi-home / diaspora
    info = venues.info(venue_id) or {}
    vcountry = info.get("country")
    if t1 == "Mexico" and vcountry == "USA":
        tilt += 0.12
        out.append({"icon": "🏟️", "text": "Quasi-home: heavy Mexican-diaspora crowd in the US", "favors": "home"})
    elif t2 == "Mexico" and vcountry == "USA":
        tilt -= 0.12
        out.append({"icon": "🏟️", "text": "Quasi-home: heavy Mexican-diaspora crowd in the US", "favors": "away"})
    elif t1 in HOST_COUNTRIES and not row["neutral"]:
        out.append({"icon": "🏟️", "text": f"Host nation {t1} at home", "favors": "home"})
    # rest
    if x["home_rest"] - x["away_rest"] >= 2:
        out.append({"icon": "😴", "text": f"{t1} better rested (+{int(x['home_rest']-x['away_rest'])}d)", "favors": "home"})
    elif x["away_rest"] - x["home_rest"] >= 2:
        out.append({"icon": "😴", "text": f"{t2} better rested (+{int(x['away_rest']-x['home_rest'])}d)", "favors": "away"})
    return out, tilt


def _neutral_row(cols):
    """A generic even match (both sides equal) as the explanation baseline."""
    base = dict.fromkeys(cols, 0.0)
    base.update(home_form=1.4, away_form=1.4, home_gf=1.3, home_ga=1.3,
                away_gf=1.3, away_ga=1.3, home_rest=14, away_rest=14,
                neutral=1, competitive=1, same_conf=0)
    return base


def explain(gbm, x_row):
    """Model-faithful 'why': ΔP(home win) contributed by each feature group,
    measured by swapping that group from a neutral baseline to the real values."""
    import pandas as pd
    cols = list(x_row.index)
    base = _neutral_row(cols)
    base_p = gbm.predict_proba(pd.DataFrame([base])[cols])[0][0]
    out = []
    for g, feats in featlib.GROUPS.items():
        row = dict(base)
        for f in feats:
            row[f] = x_row[f]
        p = gbm.predict_proba(pd.DataFrame([row])[cols])[0][0]
        out.append({"factor": g, "delta": round(float(p - base_p), 4)})
    out.sort(key=lambda d: -abs(d["delta"]))
    return {"baseline_home": round(float(base_p), 4), "contributions": out}


def build_predictions(df, ratings, dc, gbm, X, squads=None):
    squads = squads or {}
    today = dt.date.today()
    mask = (df["tournament"] == "FIFA World Cup") & (df["date"].dt.year == 2026)
    idx = np.where(mask.to_numpy())[0]
    dc_probs = np.array([dc.predict(df.iloc[i]["home_elo"], df.iloc[i]["away_elo"],
                                    bool(df.iloc[i]["neutral"]),
                                    home_team=df.iloc[i]["home_team"],
                                    away_team=df.iloc[i]["away_team"])["probs"] for i in idx])
    gbm_probs = gbm.predict_proba(X.iloc[idx])
    ens = gbmlib.ensemble(dc_probs, gbm_probs, weights=[0.6, 0.4])  # DC:GBM (tuned, experiment.py)

    preds = []
    for k, i in enumerate(idx):
        r = df.iloc[i]
        x = X.iloc[i]
        t1, t2 = r["home_team"], r["away_team"]
        venue_id = venues.resolve(r["city"])
        vinfo = venues.info(venue_id) or {}
        played = bool(r["played"])
        date_str = r["date"].date().isoformat()
        wx = None
        if venue_id:
            wx = weather.get(vinfo["lat"], vinfo["lon"], date_str,
                             hour=16, future=(r["date"].date() >= today))
        facs, tilt = _factors(r, x, wx, t1, t2, venue_id, country=r["country"])
        # squad-quality overlay (current rosters; bounded nudge + chip)
        sq1, sq2 = squads.get(t1, {}), squads.get(t2, {})
        s1, s2 = sq1.get("strength"), sq2.get("strength")
        squad_info = None
        if s1 and s2:
            tilt += max(-0.12, min(0.12, 0.5 * (s1 - s2) / 100.0))
            squad_info = {"home": s1, "away": s2,
                          "home_big5": sq1.get("n_big5"), "away_big5": sq2.get("n_big5")}
            if abs(s1 - s2) >= 4:
                fav, big5 = (t1, sq1.get("n_big5")) if s1 > s2 else (t2, sq2.get("n_big5"))
                facs.append({"icon": "⭐", "text": f"Squad quality: {fav} ({big5} top-5-league players)",
                             "favors": "home" if s1 > s2 else "away"})
        probs = _logit_tilt(list(ens[k]), tilt)
        dcp = dc.predict(r["home_elo"], r["away_elo"], bool(r["neutral"]),
                         home_team=t1, away_team=t2)
        # headline scoreline: rounded expected goals (matches real scoring); the
        # graded outcome is the one this score implies, so they never contradict
        pred_score = coherent_score(dcp["exp_home"], dcp["exp_away"])
        out_pred = score_outcome(pred_score)
        ko_score = decisive_score(dcp["grid"], dcp["exp_home"], dcp["exp_away"])
        rec = {
            "number": int(i), "date": date_str, "round": _round_label(r),
            "venue": vinfo.get("stadium"), "city": r["city"],
            "team1": t1, "team2": t2,
            "iso1": teams.iso(t1), "iso2": teams.iso(t2),
            "probs": [round(p, 4) for p in probs],
            "pred_score": pred_score, "pred_outcome": out_pred, "pred_score_ko": ko_score,
            "exp_goals": [round(dcp["exp_home"], 2), round(dcp["exp_away"], 2)],
            "elo": [round(float(r["home_elo"])), round(float(r["away_elo"]))],
            "form": [round(float(x["home_form"]), 2), round(float(x["away_form"]), 2)],
            "explain": explain(gbm, x),
            "squad": squad_info,
            "factors": facs, "played": played,
            "apparent_temp": (round(wx["apparent"]) if wx and wx.get("apparent") is not None else None),
        }
        if played:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
            o = metrics.outcome_of(hs, as_)
            rec["actual_score"] = [hs, as_]
            rec["actual_outcome"] = o
            rec["correct"] = bool(out_pred == o)            # outcome (W/D/L) called
            rec["exact_hit"] = bool(pred_score == [hs, as_])  # exact scoreline hit
            rec["rps"] = round(metrics.rps([probs], [o]), 4)
        preds.append(rec)

    accuracy = _accuracy(preds)
    return preds, accuracy


def _round_label(r):
    return "Group stage"  # refined by openfootball round in build.py merge


def _accuracy(preds):
    done = [p for p in preds if p["played"]]
    if not done:
        return {"n": 0}
    probs = np.array([p["probs"] for p in done])
    outs = np.array([p["actual_outcome"] for p in done])
    # running RPS in chronological order
    order = sorted(range(len(done)), key=lambda k: done[k]["date"])
    running, acc = [], 0.0
    for n, k in enumerate(order, 1):
        acc += done[k]["rps"]
        running.append({"date": done[k]["date"], "rps": round(acc / n, 4)})
    # calibration: predicted favourite prob vs realised hit rate
    conf = probs.max(1)
    hit = (probs.argmax(1) == outs).astype(float)
    bins = []
    for lo in (0.33, 0.45, 0.55, 0.65, 0.75, 0.85):
        hi = lo + 0.10 if lo < 0.85 else 1.01
        m = (conf >= lo) & (conf < hi)
        if m.sum():
            bins.append({"conf": round(conf[m].mean(), 3), "acc": round(hit[m].mean(), 3), "n": int(m.sum())})
    s = metrics.summary(probs, outs)   # rps/log-loss/brier/ece from the probabilities
    s["running_rps"] = running
    s["calibration"] = bins            # probability calibration (favourite prob vs win rate)
    # "result called" is graded on the projected SCORE's outcome (what's shown)
    correct = np.array([p["correct"] for p in done], float)
    s["accuracy"] = round(float(correct.mean()), 4)
    s["n_correct"] = int(correct.sum())
    # exact-scoreline accuracy (inherently low — bookmakers land ~10-13%)
    exact = [p for p in done if "exact_hit" in p]
    s["n_exact"] = sum(p["exact_hit"] for p in exact)
    s["exact_accuracy"] = round(s["n_exact"] / len(exact), 4) if exact else None
    # average goal error of the projected scoreline (both teams)
    gerr = [abs(p["pred_score"][0] - p["actual_score"][0]) + abs(p["pred_score"][1] - p["actual_score"][1])
            for p in exact]
    s["avg_goal_err"] = round(sum(gerr) / len(gerr), 2) if gerr else None
    return s


if __name__ == "__main__":
    import data, elo
    from goalmodels import XI_5Y, GoalModel
    df, ratings = elo.attach_elo(data.load_results())
    X, y = featlib.build_features(df)
    import squads as squadlib
    dc = GoalModel(attack_defence=True, ad_lambda=20, xi=XI_5Y).fit(df)
    g = gbmlib.GBM().fit(X[np.isfinite(y)], y[np.isfinite(y)])
    preds, acc = build_predictions(df, ratings, dc, g, X, squadlib.load_squads())
    print(f"2026 matches predicted: {len(preds)} | played: {acc['n']}")
    print(f"accuracy so far: RPS {acc['rps']}  acc {acc['accuracy']}  "
          f"({acc['n_correct']}/{acc['n']} outcomes)  ECE {acc['ece']}")
    up = [p for p in preds if not p["played"]][:3]
    for p in up:
        print(f"  {p['date']} {p['team1']} vs {p['team2']}: {p['probs']} "
              f"pred {p['pred_score']}  factors={[f['icon'] for f in p['factors']]}")
    assert len(preds) > 70 and acc["n"] > 50
    print("predict OK")
