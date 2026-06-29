"""World Football Elo (eloratings.net method) computed from match history.

Rating update:  Rn = Ro + K * G * (W - We)
  We = 1 / (1 + 10**(-(dr)/400)),  dr = elo_diff + home_adv(100 if not neutral)
  G  = goal-difference multiplier (1, 1.5, or (11+gd)/8 for gd>=3)
  K  = match importance (World Cup 60 ... friendly 20)

Processing rows in date order yields each team's PRE-match rating with no leakage.
"""
import pandas as pd

HOME_ADV = 100.0
BASE = 1500.0


def k_factor(tournament):
    t = (tournament or "").lower()
    if "world cup" in t and "qual" not in t:
        return 60.0
    if "confederations" in t:
        return 50.0
    if any(s in t for s in ("euro", "copa am", "african cup", "asian cup",
                            "gold cup", "nations league finals", "copa américa")):
        return 50.0 if "qual" not in t else 40.0
    if "qual" in t or "nations league" in t:
        return 40.0
    if "friendly" in t:
        return 20.0
    return 30.0


def _g_multiplier(gd):
    gd = abs(gd)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11.0 + gd) / 8.0


def attach_elo(df):
    """Return (df + home_elo/away_elo pre-match columns, final ratings dict)."""
    ratings = {}
    home_elo, away_elo = [], []
    for r in df.itertuples(index=False):
        rh = ratings.get(r.home_team, BASE)
        ra = ratings.get(r.away_team, BASE)
        home_elo.append(rh)
        away_elo.append(ra)
        if not r.played:
            continue
        dr = (rh - ra) + (0.0 if r.neutral else HOME_ADV)
        we = 1.0 / (1.0 + 10 ** (-dr / 400.0))
        gd = r.home_score - r.away_score
        w = 1.0 if gd > 0 else (0.5 if gd == 0 else 0.0)
        k = k_factor(r.tournament) * _g_multiplier(gd)
        delta = k * (w - we)
        ratings[r.home_team] = rh + delta
        ratings[r.away_team] = ra - delta
    out = df.copy()
    out["home_elo"] = home_elo
    out["away_elo"] = away_elo
    return out, ratings


def win_expectancy(elo_home, elo_away, neutral=True):
    dr = (elo_home - elo_away) + (0.0 if neutral else HOME_ADV)
    return 1.0 / (1.0 + 10 ** (-dr / 400.0))


if __name__ == "__main__":
    import data
    df = data.load_results()
    df, ratings = attach_elo(df)
    top = sorted(ratings.items(), key=lambda kv: -kv[1])[:12]
    print("Top 12 Elo (current):")
    for t, r in top:
        print(f"  {r:6.0f}  {t}")
    # sanity: a perennial top side should be highly rated
    assert ratings.get("Spain", 0) > 1900 or ratings.get("Argentina", 0) > 1900
    assert 500 < min(ratings.values()) and max(ratings.values()) < 2400
    print(f"elo OK (range {min(ratings.values()):.0f}..{max(ratings.values()):.0f})")
