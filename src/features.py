"""Leakage-safe feature builder for the GBM challenger.

Form and rest are computed in a single chronological pass so every match only
sees results strictly before it. Altitude-gap uses a country-elevation map (the
CONMEBOL-at-altitude natural experiment gives it real historical variation) plus
the precise 16-venue table for 2026. Weather/travel/diaspora are 2026-only and
live in predict.py, not here.
"""
import numpy as np
import pandas as pd

import teams
import venues

# feature groups (for the ablation in benchmark.py)
GROUPS = {
    "elo": ["elo_diff"],
    "form": ["home_form", "away_form", "form_diff", "home_gf", "home_ga", "away_gf", "away_ga"],
    "rest": ["home_rest", "away_rest", "rest_diff"],
    "context": ["neutral", "competitive", "same_conf"],
    "altitude": ["alt_gap_home", "alt_gap_away", "alt_gap_diff"],
}
ALL_FEATURES = [f for g in GROUPS.values() for f in g]

_RESTCAP = 30


def _points(gf, ga):
    return 3 if gf > ga else (1 if gf == ga else 0)


def build_features(df):
    """df must already have home_elo/away_elo. Returns (X DataFrame, y array)."""
    hist = {}   # team -> list of (date, points, gf, ga)
    last = {}   # team -> last match date
    rows = []
    for r in df.itertuples(index=False):
        h, a = r.home_team, r.away_team
        hh, ah = hist.get(h, []), hist.get(a, [])

        def form(lst):
            if not lst:
                return 1.2, 1.2, 1.2
            last5 = lst[-5:]
            return (np.mean([x[1] for x in last5]),
                    np.mean([x[2] for x in last5]),
                    np.mean([x[3] for x in last5]))
        h_form, h_gf, h_ga = form(hh)
        a_form, a_gf, a_ga = form(ah)
        h_rest = min(_RESTCAP, (r.date - last[h]).days) if h in last else _RESTCAP
        a_rest = min(_RESTCAP, (r.date - last[a]).days) if a in last else _RESTCAP

        rows.append({
            "elo_diff": (r.home_elo - r.away_elo) / 400.0,
            "home_form": h_form, "away_form": a_form, "form_diff": h_form - a_form,
            "home_gf": h_gf, "home_ga": h_ga, "away_gf": a_gf, "away_ga": a_ga,
            "home_rest": h_rest, "away_rest": a_rest, "rest_diff": h_rest - a_rest,
            "neutral": int(bool(r.neutral)),
            "competitive": int("friendly" not in (r.tournament or "").lower()),
            "same_conf": int(teams.confederation(h) == teams.confederation(a)),
            "_city": getattr(r, "city", None), "_country": getattr(r, "country", None),
        })
        if r.played:
            ph, pa = _points(r.home_score, r.away_score), _points(r.away_score, r.home_score)
            hist.setdefault(h, []).append((r.date, ph, r.home_score, r.away_score))
            hist.setdefault(a, []).append((r.date, pa, r.away_score, r.home_score))
            last[h] = last[a] = r.date

    X = pd.DataFrame(rows)
    # altitude-gap (vectorised): positive gap = playing above home base = penalty
    vid = X["_city"].map(lambda c: venues.resolve(c) if isinstance(c, str) else None)
    velev = np.array([venues.venue_elev_for_match(v, c)
                      for v, c in zip(vid, X["_country"])], float)
    h_base = df["home_team"].map(venues.country_elev).to_numpy()
    a_base = df["away_team"].map(venues.country_elev).to_numpy()
    X["alt_gap_home"] = np.maximum(0, velev - h_base) / 1000.0
    X["alt_gap_away"] = np.maximum(0, velev - a_base) / 1000.0
    X["alt_gap_diff"] = X["alt_gap_away"] - X["alt_gap_home"]
    X = X.drop(columns=["_city", "_country"])

    y = np.where(df["home_score"] > df["away_score"], 0,
                 np.where(df["home_score"] == df["away_score"], 1, 2)).astype(float)
    y[~df["played"].to_numpy()] = np.nan
    return X[ALL_FEATURES], y


if __name__ == "__main__":
    import data, elo
    df, _ = elo.attach_elo(data.load_results())
    X, y = build_features(df)
    print("features:", list(X.columns))
    print("rows:", len(X), "| labelled:", int(np.isfinite(y).sum()))
    # altitude gap must fire for CONMEBOL matches at altitude
    bol = df[(df.country == "Bolivia") & df.played].index
    if len(bol):
        assert X.loc[bol, "alt_gap_away"].mean() > 1.0, "Bolivia altitude not captured"
    assert X[features_cols := ALL_FEATURES].isna().sum().sum() == 0
    print("features OK")
