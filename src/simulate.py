"""Monte Carlo simulation of the remaining knockout bracket.

The bracket tree comes from openfootball's W##/L## references. Finished matches
are locked to their real result; the rest are sampled from the Dixon-Coles
pairwise win probabilities (neutral; draws resolved 50/50 as a shootout proxy).
Outputs each team's probability of reaching each round and winning the cup.
"""
import numpy as np

ROUND_OF = {  # match number -> round label and the "reached" milestone for its winner
    **{n: "r32" for n in range(73, 89)},
    **{n: "r16" for n in range(89, 97)},
    **{n: "qf" for n in range(97, 101)},
    **{n: "sf" for n in (101, 102)},
    103: "third", 104: "final",
}
ADVANCE = {"r32": "reach_r16", "r16": "reach_qf", "qf": "reach_sf",
           "sf": "reach_final", "final": "champion"}
MILESTONES = ["reach_r16", "reach_qf", "reach_sf", "reach_final", "champion"]


def win_prob_fn(dc, ratings):
    memo = {}
    def p1(t1, t2):
        key = (t1, t2)
        if key not in memo:
            p = dc.predict(ratings.get(t1, 1500), ratings.get(t2, 1500), neutral=True)["probs"]
            memo[key] = p[0] + 0.5 * p[1]  # draw -> coin-flip shootout
        return memo[key]
    return p1


def _resolve(slot, winner, loser, ratings):
    if slot in ratings or not (slot and slot[0] in "WL" and slot[1:].isdigit()):
        return slot
    ref = int(slot[1:])
    return winner.get(ref) if slot[0] == "W" else loser.get(ref)


def simulate(bracket, dc, ratings, n=20000, seed=0):
    p1 = win_prob_fn(dc, ratings)
    ko = sorted([m for m in bracket if m["number"] >= 73], key=lambda m: m["number"])
    rng = np.random.default_rng(seed)
    tally = {}  # team -> {milestone: count}

    def bump(team, ms):
        tally.setdefault(team, {k: 0 for k in MILESTONES})[ms] += 1

    for _ in range(n):
        winner, loser = {}, {}
        for m in ko:
            num = m["number"]
            t1 = _resolve(m["team1"], winner, loser, ratings)
            t2 = _resolve(m["team2"], winner, loser, ratings)
            if t1 is None or t2 is None:
                continue
            if m["home_score"] is not None:  # locked real result
                w, l = (t1, t2) if m["home_score"] >= m["away_score"] else (t2, t1)
            else:
                w, l = (t1, t2) if rng.random() < p1(t1, t2) else (t2, t1)
            winner[num], loser[num] = w, l
            r = ROUND_OF[num]
            if r in ADVANCE:
                bump(w, ADVANCE[r])

    out = {}
    for team, c in tally.items():
        out[team] = {k: round(c[k] / n, 4) for k in MILESTONES}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["champion"]))


if __name__ == "__main__":
    import data, elo
    from model import DixonColes
    df, ratings = elo.attach_elo(data.load_results())
    dc = DixonColes().fit(df)
    bracket = data.load_wc2026()
    odds = simulate(bracket, dc, ratings, n=5000)
    print("Championship odds (top 12):")
    for t, o in list(odds.items())[:12]:
        print(f"  {o['champion']*100:5.1f}%  reach_final {o['reach_final']*100:4.1f}%   {t}")
    tot = sum(o["champion"] for o in odds.values())
    assert abs(tot - 1.0) < 0.02, tot          # exactly one champion per sim
    print(f"sum champion = {tot:.3f}  -> simulate OK")
