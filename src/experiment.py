"""Ambitious model-improvement experiments — run honestly, keep only what helps.

Killian's ask: predict more of the upsets / be less "safe", be ambitious. The
honest tension: a calibrated model SHOULD favour favourites. So we test, on real
walk-forward data, whether the model is over-confident (=> softening gives
underdogs more probability AND improves RPS) and whether recency / ensemble
weighting help. One walk-forward collects base DC + GBM probs; everything else is
evaluated post-hoc (cheap). Results printed + written to reports/experiment.json.
"""
import json
import os

import numpy as np
import pandas as pd

import data
import elo
import features as featlib
import gbm as gbmlib
import metrics
from model import DixonColes

OUT = os.path.join(os.path.dirname(__file__), "..", "reports", "experiment.json")


def collect(df, X, y, years=4, retrain_days=90):
    """Walk-forward; return per-test-match dc probs, gbm probs, outcomes, fav prob."""
    played = df["played"].to_numpy()
    dates = df["date"]
    end = dates.max()
    start = end - pd.Timedelta(days=int(365.25 * years))
    edges = pd.date_range(start, end + pd.Timedelta(days=retrain_days), freq=f"{retrain_days}D")
    DC, GB, OUT_, ISKO = [], [], [], []
    for b0, b1 in zip(edges[:-1], edges[1:]):
        te = played & (dates >= b0).to_numpy() & (dates < b1).to_numpy()
        tr = played & (dates < b0).to_numpy()
        if te.sum() == 0 or tr.sum() < 2000:
            continue
        tri, tei = np.where(tr)[0], np.where(te)[0]
        dc = DixonColes().fit(df.iloc[tri])
        gb = gbmlib.GBM().fit(X.iloc[tri], y[tri])
        sub = df.iloc[tei]
        DC.append(np.array([dc.predict(r.home_elo, r.away_elo, bool(r.neutral))["probs"]
                            for r in sub.itertuples()]))
        GB.append(gb.predict_proba(X.iloc[tei]))
        OUT_.append(y[tei].astype(int))
        ISKO.append(sub["tournament"].str.contains("World Cup|Euro|Copa|Nations", case=False).to_numpy())
    return (np.vstack(DC), np.vstack(GB), np.concatenate(OUT_), np.concatenate(ISKO))


def temperature(probs, T):
    p = np.clip(probs, 1e-9, 1) ** (1.0 / T)
    return p / p.sum(1, keepdims=True)


def main():
    df, _ = elo.attach_elo(data.load_results())
    X, y = featlib.build_features(df)
    dc, gb, out, isko = collect(df, X, y)
    n = len(out)
    print(f"walk-forward test matches: {n}\n")

    base = lambda w: gbmlib.ensemble(dc, gb, weights=[w, 1 - w])
    res = {}

    # 1) ensemble weight sweep
    print("ensemble weight (DC share) -> RPS")
    best_w, best = 0.5, 9
    for w in [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0]:
        r = metrics.rps(base(w), out)
        print(f"  w={w:.1f}  RPS {r:.4f}")
        if r < best:
            best, best_w = r, w
    res["best_weight"] = best_w

    # 2) temperature on the best ensemble (T>1 = model was over-confident -> more upsets)
    ens = base(best_w)
    print("\ntemperature scaling (T>1 softens => more upset probability)")
    bestT, bestTr = 1.0, metrics.rps(ens, out)
    for T in [0.8, 0.9, 1.0, 1.1, 1.2, 1.35, 1.5]:
        r = metrics.rps(temperature(ens, T), out)
        print(f"  T={T:.2f}  RPS {r:.4f}  ECE {metrics.ece(temperature(ens, T), out):.3f}")
        if r < bestTr:
            bestTr, bestT = r, T
    res["best_temperature"] = bestT

    # 3) upset calibration: when the favourite is X% likely, how often do they actually win?
    print("\nupset calibration (favourite predicted vs actual win rate)")
    fav = ens.max(1)
    favhit = (ens.argmax(1) == out).astype(float)
    cal = []
    for lo in [0.4, 0.5, 0.6, 0.7, 0.8]:
        hi = lo + 0.1
        m = (fav >= lo) & (fav < hi)
        if m.sum() > 15:
            row = {"band": f"{lo:.0%}-{hi:.0%}", "pred": round(fav[m].mean(), 3),
                   "actual": round(favhit[m].mean(), 3), "n": int(m.sum())}
            cal.append(row)
            flag = "UPSETS UNDER-PRED" if row["actual"] < row["pred"] - 0.04 else ""
            print(f"  fav {row['band']}: predicted {row['pred']:.0%} win, actual {row['actual']:.0%} ({row['n']}) {flag}")
    res["calibration"] = cal

    # 4) does a knockout-specific temperature help? (KO games are higher-variance)
    print("\nknockout-only temperature (big-tournament matches)")
    if isko.sum() > 30:
        for T in [1.0, 1.2, 1.4]:
            p = ens.copy()
            p[isko] = temperature(ens[isko], T)
            print(f"  KO T={T:.1f}  RPS(all) {metrics.rps(p, out):.4f}  RPS(KO-only) {metrics.rps(temperature(ens[isko], T), out[isko]):.4f}")

    res["base_rps"] = round(metrics.rps(ens, out), 4)
    res["tuned_rps"] = round(metrics.rps(temperature(base(best_w), bestT), out), 4)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nbase RPS {res['base_rps']} -> tuned (w={best_w}, T={bestT}) {res['tuned_rps']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
