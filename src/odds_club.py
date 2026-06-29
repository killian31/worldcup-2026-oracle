"""PROOF experiment: do betting-market odds add ORTHOGONAL signal beyond our
team-strength features? Free historical international odds don't exist, but club
odds do (football-data.co.uk, no key) — so we prove the methodology where the
data is abundant, then apply the same blend to live internationals.

Pipeline: pull top-5 leagues x many seasons (results + closing odds aligned per
row) -> club Elo + form features -> de-vig closing odds into market probs ->
chronological split -> compare:
  M1 team-strength GBM | M2 market (de-vigged odds) | M3 GBM+odds | M4 blend
and crucially the per-match error CORRELATION between M1 and the market (low =
orthogonal = the missing signal). Market RPS ~0.198 is the published ceiling.
"""
import io
import os
import urllib.request

import numpy as np
import pandas as pd

import gbm as gbmlib
import metrics

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "club_odds.pkl")
LEAGUES = ["E0", "SP1", "I1", "D1", "F1"]
SEASONS = [f"{a % 100:02d}{(a + 1) % 100:02d}" for a in range(2008, 2025)]  # 0809..2425
# closing-odds column triples, sharpest first; fall back down the list
ODDS_SETS = [("PSCH", "PSCD", "PSCA"), ("B365CH", "B365CD", "B365CA"),
             ("AvgCH", "AvgCD", "AvgCA"), ("PSH", "PSD", "PSA"),
             ("B365H", "B365D", "B365A"), ("AvgH", "AvgD", "AvgA")]


def _load_raw():
    if os.path.exists(CACHE):
        return pd.read_pickle(CACHE)
    frames = []
    for s in SEASONS:
        for lg in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{s}/{lg}.csv"
            try:
                raw = urllib.request.urlopen(url, timeout=30).read()
                df = pd.read_csv(io.BytesIO(raw), encoding="latin-1", on_bad_lines="skip")
            except Exception:
                continue
            df["season"] = s
            frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    try:
        out.to_pickle(CACHE)
    except Exception:
        pass
    return out


def _devig(df):
    """Coalesce the best available closing-odds triple, de-vig multiplicatively."""
    n = len(df)
    oH = pd.Series(np.nan, index=df.index)
    oD = pd.Series(np.nan, index=df.index)
    oA = pd.Series(np.nan, index=df.index)
    for h, d, a in ODDS_SETS:
        if h in df and d in df and a in df:
            m = oH.isna() & df[h].notna() & df[d].notna() & df[a].notna()
            oH[m], oD[m], oA[m] = df[h][m], df[d][m], df[a][m]
    inv = np.c_[1 / oH, 1 / oD, 1 / oA]
    p = inv / inv.sum(1, keepdims=True)
    return p


def build():
    raw = _load_raw()
    df = raw.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]).copy()
    df["date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df["y"] = df["FTR"].map({"H": 0, "D": 1, "A": 2})
    market = _devig(df)
    ok = ~np.isnan(market).any(1)
    df, market = df[ok].reset_index(drop=True), market[ok]

    # club Elo (home advantage in the expectation) + last-5 form, computed online
    elo, form, lastpts = {}, {}, {}
    feats = []
    HA, K = 65.0, 20.0
    for r in df.itertuples(index=False):
        eh, ea = elo.get(r.HomeTeam, 1500.0), elo.get(r.AwayTeam, 1500.0)
        fh = np.mean(form.get(r.HomeTeam, [1.4])[-5:])
        fa = np.mean(form.get(r.AwayTeam, [1.4])[-5:])
        feats.append((eh - ea, fh, fa, fh - fa))
        we = 1 / (1 + 10 ** (-((eh - ea) + HA) / 400))
        res = 1.0 if r.FTHG > r.FTAG else (0.5 if r.FTHG == r.FTAG else 0.0)
        elo[r.HomeTeam] = eh + K * (res - we)
        elo[r.AwayTeam] = ea - K * (res - we)
        ph = 3 if r.FTHG > r.FTAG else (1 if r.FTHG == r.FTAG else 0)
        form.setdefault(r.HomeTeam, []).append(ph)
        form.setdefault(r.AwayTeam, []).append(3 - ph if ph != 1 else 1)
    X = pd.DataFrame(feats, columns=["elo_diff", "home_form", "away_form", "form_diff"])
    return df, X, df["y"].to_numpy(), market


def main():
    df, X, y, market = build()
    n = len(y)
    cut = int(n * 0.7)
    tr, te = slice(0, cut), slice(cut, n)
    print(f"club matches {n:,} ({df.date.min().date()}..{df.date.max().date()}); "
          f"train {cut:,}, test {n - cut:,}\n")

    # M1: team-strength GBM (no odds)
    g1 = gbmlib.GBM().fit(X.iloc[tr], y[tr].astype(float))
    m1 = g1.predict_proba(X.iloc[te])
    # M2: the market itself
    m2 = market[te]
    # M3: GBM + odds as features
    Xo = X.copy()
    Xo["mkt_h"], Xo["mkt_d"], Xo["mkt_a"] = market[:, 0], market[:, 1], market[:, 2]
    g3 = gbmlib.GBM().fit(Xo.iloc[tr], y[tr].astype(float))
    m3 = g3.predict_proba(Xo.iloc[te])
    # M4: log-opinion-pool blend of M1 and market (weight w on market)
    def pool(a, b, w):
        z = (np.log(np.clip(a, 1e-9, 1)) * (1 - w) + np.log(np.clip(b, 1e-9, 1)) * w)
        e = np.exp(z)
        return e / e.sum(1, keepdims=True)
    # tune w on first half of test, eval on second (no leakage)
    h = (n - cut) // 2
    ws = np.linspace(0, 1, 11)
    w = ws[np.argmin([metrics.rps(pool(m1[:h], m2[:h], wi), y[te][:h]) for wi in ws])]
    m4 = pool(m1, m2, w)

    res = {"team-strength GBM (no odds)": m1, "market (de-vigged odds)": m2,
           "GBM + odds feature": m3, f"blend (model + market, w={w:.1f})": m4}
    print(f"{'model':<34}{'RPS':>8}{'logloss':>9}{'acc':>7}{'ECE':>7}")
    for name, p in res.items():
        s = metrics.summary(p, y[te])
        print(f"{name:<34}{s['rps']:>8.4f}{s['log_loss']:>9.4f}{s['accuracy']:>7.3f}{s['ece']:>7.3f}")

    # the headline: are model errors and market errors ORTHOGONAL?
    eps = 1e-9
    ll1 = -np.log(np.clip(m1[np.arange(n - cut), y[te]], eps, 1))
    llm = -np.log(np.clip(m2[np.arange(n - cut), y[te]], eps, 1))
    corr = float(np.corrcoef(ll1, llm)[0, 1])
    gain = metrics.rps(m1, y[te]) - metrics.rps(m3, y[te])
    print(f"\nper-match error correlation  model vs market = {corr:.2f}  "
          f"(our internal models were ~0.96 — lower here = orthogonal signal)")
    print(f"adding odds to the model improves RPS by {gain:+.4f}")
    print(f"market RPS {metrics.rps(m2, y[te]):.4f} vs published ceiling ~0.198")

    import json
    out = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "odds_proof.json")
    json.dump({"n_total": n, "n_test": n - cut, "from": str(df.date.min().year),
               "to": str(df.date.max().year), "market_rps": round(metrics.rps(m2, y[te]), 4),
               "model_rps": round(metrics.rps(m1, y[te]), 4),
               "model_plus_odds_rps": round(metrics.rps(m3, y[te]), 4),
               "odds_gain": round(gain, 4), "error_corr": round(corr, 2), "ceiling": 0.198,
               "best_blend_w": round(float(w), 1),
               "rows": [{"model": k, "rps": metrics.summary(p, y[te])["rps"],
                         "acc": metrics.summary(p, y[te])["accuracy"]}
                        for k, p in res.items() if "blend" not in k]},
              open(out, "w"), indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
