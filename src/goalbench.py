"""Exact-score bake-off — does overdispersion and/or team attack/defence beat the
production Elo->Poisson Dixon-Coles at *scorelines*? Walk-forward, no leakage:
train on everything strictly before each block, score the block.

Metrics (1X2 RPS is shown but is NOT the point — odds cap that; the score grid is
where the model still owns turf):
  score_ll  mean -log P(actual exact score) under the grid  (distribution quality; primary)
  exact%    modal grid cell == actual scoreline
  goal_mae  |round(E[home])-home| + |round(E[away])-away|   (the displayed score)
  draw%     mean predicted draw prob   (vs the realised draw rate, for sanity)
"""
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

import data
import elo
import metrics
from goalmodels import XI_5Y, GoalModel
from model import MAXG, _round_half_up

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "goalbench.json")
XI_1Y = math.log(2) / 365.0  # the previous production decay (1-year half-life)
# Narrative bake-off: previous production -> each lever in turn -> the shipped config.
BASELINE, SHIPPED = "Elo → Poisson (previous)", "+ 5-year memory (shipped)"
MODELS = {BASELINE: dict(attack_defence=False, negbin=False, xi=XI_1Y),
          "+ team attack / defence": dict(attack_defence=True, negbin=False, xi=XI_1Y),
          SHIPPED: dict(attack_defence=True, negbin=False, xi=XI_5Y),
          "+ Negative-Binomial": dict(attack_defence=True, negbin=True, xi=XI_5Y)}


def _accumulate(store, p, hs, as_):
    store["probs"].append(p["probs"])
    store["out"].append(0 if hs > as_ else (1 if hs == as_ else 2))
    g = p["grid"]
    store["pscore"].append(float(g[min(hs, MAXG), min(as_, MAXG)]))
    mh, ma = p["top_score"]
    store["exact"].append(1.0 if (mh == hs and ma == as_) else 0.0)
    store["mae"].append(abs(_round_half_up(p["exp_home"]) - hs) + abs(_round_half_up(p["exp_away"]) - as_))
    store["pdraw"].append(p["probs"][1])


def _summary(store):
    probs = np.array(store["probs"]); outs = np.array(store["out"])
    ps = np.clip(np.array(store["pscore"]), 1e-12, 1)
    return {"n": len(outs),
            "rps": round(metrics.rps(probs, outs), 4),
            "score_ll": round(float(np.mean(-np.log(ps))), 4),
            "exact_pct": round(float(np.mean(store["exact"])), 4),
            "goal_mae": round(float(np.mean(store["mae"])), 3),
            "pred_draw": round(float(np.mean(store["pdraw"])), 4),
            "real_draw": round(float(np.mean(outs == 1)), 4)}


def run(df, years=5.0, retrain_days=120, ad_lambda=50.0, models=MODELS):
    played = df["played"].to_numpy()
    dates = df["date"]
    end = dates.max(); start = end - pd.Timedelta(days=int(365.25 * years))
    edges = pd.date_range(start, end + pd.Timedelta(days=retrain_days), freq=f"{retrain_days}D")
    acc = {m: defaultdict(list) for m in models}
    for b0, b1 in zip(edges[:-1], edges[1:]):
        te = played & (dates >= b0).to_numpy() & (dates < b1).to_numpy()
        tr = played & (dates < b0).to_numpy()
        if te.sum() == 0 or tr.sum() < 3000:
            continue
        df_tr, df_te = df.iloc[np.where(tr)[0]], df.iloc[np.where(te)[0]]
        for m, opt in models.items():
            gm = GoalModel(ad_lambda=ad_lambda, **opt).fit(df_tr)
            for r in df_te.itertuples():
                p = gm.predict(r.home_elo, r.away_elo, bool(r.neutral),
                               home_team=r.home_team, away_team=r.away_team)
                _accumulate(acc[m], p, int(r.home_score), int(r.away_score))
        print(f"  block {b0.date()}..{b1.date()}: train {len(df_tr)} test {len(df_te)}")
    return {m: _summary(s) for m, s in acc.items()}


def main():
    years = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    df, _ = elo.attach_elo(data.load_results())
    # ad_lambda=20 chosen by an earlier shrinkage sweep (lighter shrinkage won).
    print(f"goal-model bake-off (walk-forward {years}y, attack/defence lam=20):")
    res = run(df, years=years, ad_lambda=20.0)

    print(f"\n{'model':<28}{'RPS':>8}{'score_ll':>10}{'exact%':>9}{'goal_mae':>10}{'n':>7}")
    base = res[BASELINE]
    for m, s in res.items():
        dll = s["score_ll"] - base["score_ll"]
        print(f"{m:<28}{s['rps']:>8.4f}{s['score_ll']:>10.4f}{s['exact_pct']*100:>8.2f}%"
              f"{s['goal_mae']:>10.3f}{s['n']:>7d}   dscore_ll {dll:+.4f}")

    payload = {"years": years, "ad_lambda": 20.0, "n": base["n"],
               "baseline": BASELINE, "shipped": SHIPPED,
               "models": res, "winner": SHIPPED,
               "rows": [{"model": m, **s} for m, s in res.items()]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(payload, open(OUT, "w"), indent=2)
    print(f"\nshipped: {SHIPPED}  ->  wrote {OUT}")


if __name__ == "__main__":
    main()
