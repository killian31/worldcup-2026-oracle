"""Optional LIVE market-odds blend for the 2026 predictions.

Free historical international odds don't exist, so odds can't be back-tested for
internationals — but the club proof (odds_club.py) establishes the method, and we
can still blend LIVE market odds into the upcoming-match forecasts. Requires a
free The Odds API key in env ODDS_API_KEY; with no key this returns {} and the
pipeline runs exactly as before (the blend is purely additive).
"""
import json
import os
import urllib.request

import numpy as np

import teams

SPORT = "soccer_fifa_world_cup"
URL = ("https://api.the-odds-api.com/v4/sports/{sport}/odds"
       "?apiKey={key}&regions=eu&markets=h2h&oddsFormat=decimal")
# weight on the market in the log-opinion-pool blend (from odds_club.py backtest)
BLEND_W = float(os.environ.get("ODDS_BLEND_W", "0.6"))
# The Odds API spellings that differ from martj42 canonical names
EXTRA = {"USA": "United States", "South Korea": "Korea Republic", "Korea Republic": "South Korea",
         "IR Iran": "Iran", "Czechia": "Czech Republic", "Turkiye": "Turkey",
         "Cote d'Ivoire": "Ivory Coast", "Cape Verde Islands": "Cape Verde"}


def _canon(name):
    return teams.normalize(EXTRA.get(name, name))


def _devig(odds):
    inv = np.array([1 / o for o in odds], float)
    return (inv / inv.sum()).tolist()


def fetch_market(api_key=None):
    """Return {(home, away): [pH, pD, pA]} de-vigged, averaged across bookmakers.
    Keyed by canonical team names. {} on any failure / missing key."""
    api_key = api_key or os.environ.get("ODDS_API_KEY")
    if not api_key:
        return {}
    try:
        with urllib.request.urlopen(URL.format(sport=SPORT, key=api_key), timeout=25) as r:
            events = json.load(r)
    except Exception as e:
        print(f"odds: live fetch failed ({e}); skipping blend")
        return {}
    out = {}
    for ev in events:
        home, away = _canon(ev.get("home_team")), _canon(ev.get("away_team"))
        acc = {}  # outcome name -> [prices]
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                if mk.get("key") != "h2h":
                    continue
                for oc in mk.get("outcomes", []):
                    acc.setdefault(oc["name"], []).append(oc["price"])
        if not acc:
            continue
        avg = {k: float(np.mean(v)) for k, v in acc.items()}
        # outcomes are home name / away name / "Draw"
        try:
            oh = avg[ev["home_team"]]
            oa = avg[ev["away_team"]]
            od = avg["Draw"]
        except KeyError:
            continue
        out[(home, away)] = _devig([oh, od, oa])
    return out


def blend(model_probs, market_probs, w=BLEND_W):
    """Log-opinion-pool of model and market probabilities."""
    a = np.clip(model_probs, 1e-9, 1)
    b = np.clip(market_probs, 1e-9, 1)
    z = np.log(a) * (1 - w) + np.log(b) * w
    e = np.exp(z)
    return (e / e.sum()).tolist()


if __name__ == "__main__":
    mkt = fetch_market()
    if not mkt:
        print("No ODDS_API_KEY set (or fetch failed) — live blend is disabled, pipeline unaffected.")
    else:
        print(f"fetched market odds for {len(mkt)} matches; e.g. {list(mkt.items())[:2]}")
