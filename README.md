# 🔮 World Cup 2026 Oracle

A self-updating model + broadcast-style web app that predicts the **2026 FIFA World Cup**,
tracks its own **accuracy in real time**, and shows *why* it favours each side. Runs on
**$0** — public-domain data, free hosting, no API keys.

**Live site:** _enable GitHub Pages (branch `main`, folder `/docs`) — see Deploy below._

Tabs: **Upcoming · Results · Simulate · Odds & Bracket · Groups · Squads · Accuracy · Model · History**

## What it does

- **Predicts every match** — win/draw/win probabilities + a realistic projected scoreline
  (`round(expected goals)`, not the Poisson-compressed modal score) and expected goals, from a
  calibrated Elo → Dixon-Coles + gradient-boosting **ensemble**.
- **Explains every prediction** — a per-match "Why?" panel quantifying how much each factor (Elo
  gap, form, rest, altitude…) shifted the win probability, plus the raw Elo/form/squad inputs.
- **Plays the tournament** — an animated **Simulate** tab: press play and watch the bracket roll
  from the current round to a champion, sampling each remaining match from the model; replay to
  build a champions tally.
- **Knows the squads** — a player layer from openfootball's 26-man rosters: each team's squad, club,
  and a squad-strength index (league quality of each player's club; a free, no-secret proxy that
  correlates ~0.67 with Elo and nudges predictions as a 2026-only overlay).
- **Simulates the tournament** — 50k Monte-Carlo runs over the live bracket → each team's odds to
  reach each round and win the cup.
- **Grades itself honestly** — retro-predicts every already-played 2026 match using only
  pre-kickoff information and shows running **RPS**, hit-rate, and a calibration plot.
- **Surfaces innovative factors most models ignore** — altitude, heat (Open-Meteo), rest, squad
  quality, and the Mexican-diaspora quasi-home crowd — shown as "why" chips on each card.

## The model

| Stage | Choice | Why |
|---|---|---|
| Rating | World-Football **Elo** from 49k internationals (1872→now) | strongest single predictor |
| Goals | **Dixon-Coles** (Poisson GLM on Elo + home/host, time-decay, low-score ρ) | proven for football scores |
| Challenger | **HistGradientBoosting** on Elo/form/rest/altitude/context | catches non-linear interactions |
| Final | **probability-averaged ensemble**, calibration checked | beats either model alone |
| Tournament | **Monte-Carlo** over openfootball's W##/L## bracket tree | championship odds |

### Benchmark (walk-forward, ~3 251 internationals, 2023→2026)

| model | RPS ↓ | log-loss | acc | ECE |
|---|---|---|---|---|
| baseline (base-rate) | 0.2282 | 1.054 | 47% | — |
| Dixon-Coles | 0.1673 | 0.865 | 61% | 1.0% |
| HistGBM | 0.1670 | 0.861 | 60% | 2.2% |
| **ensemble ⭐** | **0.1664** | 0.860 | 60% | 1.4% |

**Feature ablation** (RPS cost of removing a group): Elo **+0.0332** (dominant), form +0.0008,
rest/altitude +0.0003, context +0.0001. Honest takeaway: Elo carries the model; form, rest and the
altitude-gap feature add small-but-real signal — exactly as the literature predicts (altitude only
bites at the two Mexican venues). Weather/travel/diaspora vary only in 2026, so they're applied as
transparent per-match factors, not baked into the historical training.

## Data (all free, no key)

- [martj42/international_results](https://github.com/martj42/international_results) — match history
  **and** 2026 results (CC0).
- [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json) — 2026 bracket tree (CC0).
- [Open-Meteo](https://open-meteo.com) — venue weather (no key).

football-data.org is supported as an optional live-status source but is **not required** — the app
updates from the public-domain feeds alone.

## Run locally

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/build.py            # writes docs/data/*.json
python -m http.server -d docs 8000   # open http://localhost:8000
```

Each `src/*.py` has a `__main__` self-check (`python src/model.py`, etc.).
Re-run the slow benchmark with `python src/benchmark.py 3` (writes `docs/data/benchmark.json`).

## Deploy (GitHub Pages, free)

1. Push to a **public** repo named `worldcup-2026-oracle`.
2. **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`.**
3. That's it. `.github/workflows/update.yml` refreshes the data twice an hour and commits it back;
   each commit auto-deploys. No secrets needed.

## Layout

```
src/        teams, venues, data, elo, features, model, gbm, squads, simulate, predict, benchmark, build, metrics, weather
docs/       index.html · style.css · app.js · data/*.json   (Pages root)
.github/    update.yml
```

### A note on player "form" and injuries
Per-player current form and live injuries have **no clean free feed** (FBref's advanced stats were
discontinued in Jan 2026; the rest is paywalled or fragile scraping). So the player layer uses what
*is* free and robust — squad rosters + club-league strength — and team-level recent form is already
in the model. Per-player form/availability is a documented phase-2 item, not faked.

_Predictions are probabilistic and for fun — not betting advice._
