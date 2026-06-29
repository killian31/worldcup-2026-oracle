"""Walk-forward benchmark + feature ablation — the honest hypothesis test.

Rolling-origin: for each time block in the test window, train on everything
strictly before it and predict the block (no leakage; features are already
pre-match). Compares Baseline / Poisson / Dixon-Coles / GBM / Ensemble on RPS
(primary), log-loss, Brier, accuracy, ECE. The ablation removes one feature group
at a time from the GBM and reports the RPS change, so "does altitude/rest/form
actually help" is answered with numbers, not assertion.

Run on demand (slow); results are committed to docs/data/benchmark.json and the
fast CI build reuses them.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

import data
import elo
import features
import gbm as gbmlib
import metrics
from model import DixonColes

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "benchmark.json")


def _blocks(dates, years, retrain_days):
    end = dates.max()
    start = end - pd.Timedelta(days=int(365.25 * years))
    edges = pd.date_range(start, end + pd.Timedelta(days=retrain_days), freq=f"{retrain_days}D")
    return start, list(zip(edges[:-1], edges[1:]))


def walkforward(df, X, y, years=3, retrain_days=90, feature_cols=None, models=None):
    feature_cols = feature_cols or features.ALL_FEATURES
    models = models or ["baseline", "poisson", "dixoncoles", "gbm", "ensemble"]
    played = df["played"].to_numpy()
    dates = df["date"]
    start, blocks = _blocks(dates, years, retrain_days)
    preds = {m: [] for m in models}
    outs, kept_dates = [], []

    for b0, b1 in blocks:
        test_mask = played & (dates >= b0).to_numpy() & (dates < b1).to_numpy()
        train_mask = played & (dates < b0).to_numpy()
        if test_mask.sum() == 0 or train_mask.sum() < 2000:
            continue
        tr, te = np.where(train_mask)[0], np.where(test_mask)[0]
        df_tr = df.iloc[tr]
        eh, ea, neu = (df.iloc[te]["home_elo"].to_numpy(),
                       df.iloc[te]["away_elo"].to_numpy(),
                       df.iloc[te]["neutral"].to_numpy())

        dc = poi = gb = None
        if "dixoncoles" in models or "ensemble" in models:
            dc = DixonColes().fit(df_tr)
        if "poisson" in models:
            poi = DixonColes(xi=0.0).fit(df_tr); poi.rho = 0.0
        if "gbm" in models or "ensemble" in models:
            gb = gbmlib.GBM().fit(X.iloc[tr][feature_cols], y[tr])

        def dc_pred(m):
            return np.array([m.predict(h, a, bool(n))["probs"] for h, a, n in zip(eh, ea, neu)])

        block = {}
        if "baseline" in models:
            freq = np.bincount(y[tr].astype(int), minlength=3) / len(tr)
            block["baseline"] = np.tile(freq, (len(te), 1))
        if "poisson" in models:
            block["poisson"] = dc_pred(poi)
        if dc is not None:
            block["dixoncoles"] = dc_pred(dc)
        if gb is not None:
            block["gbm"] = gb.predict_proba(X.iloc[te][feature_cols])
        if "ensemble" in models:
            block["ensemble"] = gbmlib.ensemble(block["dixoncoles"], block["gbm"])

        for m in models:
            preds[m].append(block[m])
        outs.append(y[te].astype(int))
        kept_dates.append(df.iloc[te]["date"].to_numpy())

    outcomes = np.concatenate(outs)
    results = {m: metrics.summary(np.concatenate(preds[m]), outcomes) for m in models}
    return results, np.concatenate(kept_dates), outcomes


def ablation(df, X, y, years=3, retrain_days=90):
    """RPS of the GBM with each feature group removed (positive delta = group helps)."""
    full, _, _ = walkforward(df, X, y, years, retrain_days, models=["gbm"])
    base_rps = full["gbm"]["rps"]
    out = {"full": base_rps, "groups": {}}
    for g, cols in features.GROUPS.items():
        keep = [c for c in features.ALL_FEATURES if c not in cols]
        r, _, _ = walkforward(df, X, y, years, retrain_days, feature_cols=keep, models=["gbm"])
        out["groups"][g] = {"rps_without": r["gbm"]["rps"],
                            "delta": round(r["gbm"]["rps"] - base_rps, 4)}
    return out


def main():
    years = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    df, _ = elo.attach_elo(data.load_results())
    X, y = features.build_features(df)

    print(f"Walk-forward benchmark — last {years}y, retrain every 90d\n")
    results, dates, outcomes = walkforward(df, X, y, years=years)
    print(f"{'model':<12}{'RPS':>8}{'logloss':>9}{'brier':>8}{'acc':>7}{'ECE':>7}{'n':>7}")
    for m, s in results.items():
        print(f"{m:<12}{s['rps']:>8.4f}{s['log_loss']:>9.4f}{s['brier']:>8.4f}"
              f"{s['accuracy']:>7.3f}{s['ece']:>7.3f}{s['n']:>7d}")

    print("\nFeature ablation (RPS rise when a group is removed; + = it helps):")
    abl = ablation(df, X, y, years=years)
    for g, d in abl["groups"].items():
        print(f"  {g:<10} without={d['rps_without']:.4f}  delta={d['delta']:+.4f}")

    best = min(results, key=lambda m: results[m]["rps"])
    payload = {"test_window_years": years, "n_matches": int(len(outcomes)),
               "date_from": str(pd.Timestamp(dates.min()).date()),
               "date_to": str(pd.Timestamp(dates.max()).date()),
               "models": results, "best_model": best, "ablation": abl}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(payload, open(OUT, "w"), indent=2)
    print(f"\nbest by RPS: {best}  ->  wrote {OUT}")

    assert results["ensemble"]["rps"] < results["baseline"]["rps"], "ensemble must beat naive"
    print("benchmark OK")


if __name__ == "__main__":
    main()
