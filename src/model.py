"""Elo -> Dixon-Coles goal model.

1. A symmetric Poisson GLM maps each side's (Elo advantage, home field) to its
   expected goals, fit on all history with exponential time-decay sample weights.
2. Independent-Poisson score grid, then the Dixon-Coles low-score correlation
   correction (rho, fit by MLE), giving W/D/L and exact-scoreline probabilities.

Host advantage is captured for free: martj42 flags host matches as non-neutral,
so the home-field term applies to USA/Mexico/Canada at home.
"""
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor

MAXG = 10          # score-grid cap
ELO_SCALE = 400.0  # logistic Elo scale
DEFAULT_XI = 0.0019  # time-decay per day (~1y half-life)


def _round_half_up(x):
    return int(np.floor(x + 0.5))


def most_likely_score(grid, outcome):
    """Most probable exact scoreline *within* the predicted outcome region
    (0=home win, 1=draw, 2=away win) — accuracy-optimal but visually low-scoring."""
    g = np.asarray(grid)
    ii, jj = np.indices(g.shape)
    mask = ii > jj if outcome == 0 else (ii == jj if outcome == 1 else ii < jj)
    i, j = np.unravel_index(np.argmax(np.where(mask, g, -1.0)), g.shape)
    return [int(i), int(j)]


def coherent_score(exp_home, exp_away):
    """Headline scoreline = rounded EXPECTED goals. Its goal totals match real
    scoring (~2.8/game, vs the Poisson mode's unrealistic ~1.4) and it shows draws
    at the true ~28% rate. The displayed outcome (who it implies wins) is what gets
    graded, so the score and the verdict are always consistent."""
    return [_round_half_up(exp_home), _round_half_up(exp_away)]


def score_outcome(score):
    return 0 if score[0] > score[1] else (1 if score[0] == score[1] else 2)


def decisive_score(grid, exp_home, exp_away):
    """Knockout scoreline (no draws — KO games resolve to a winner). Use rounded
    expected goals when that's already decisive (2-1, 3-0, 1-2 for clearer games);
    otherwise the single most-likely non-draw scoreline from the grid (1-0, 2-0…
    for tight games). Gives a realistic, varied mix instead of a 2-1 monoculture."""
    h, a = _round_half_up(exp_home), _round_half_up(exp_away)
    if h != a:
        return [h, a]
    g = np.array(grid, dtype=float).copy()
    np.fill_diagonal(g, 0.0)
    i, j = np.unravel_index(np.argmax(g), g.shape)
    return [int(i), int(j)]


def _home_field(neutral, is_home):
    if neutral:
        return 0.0
    return 1.0 if is_home else -1.0


class DixonColes:
    def __init__(self, xi=DEFAULT_XI, alpha=1e-4):
        self.xi = xi
        self.alpha = alpha
        self.glm = None
        self.rho = 0.0

    def _design(self, elo_self, elo_opp, home_field):
        elo_self = np.asarray(elo_self, float)
        elo_opp = np.asarray(elo_opp, float)
        return np.column_stack([(elo_self - elo_opp) / ELO_SCALE, np.asarray(home_field, float)])

    def fit(self, df):
        d = df[df["played"]].copy()
        ref = d["date"].max()
        age = (ref - d["date"]).dt.days.to_numpy()
        w = np.exp(-self.xi * age)
        # stack home-attacking and away-attacking perspectives
        hf_home = [_home_field(n, True) for n in d["neutral"]]
        hf_away = [_home_field(n, False) for n in d["neutral"]]
        X = np.vstack([
            self._design(d["home_elo"].to_numpy(), d["away_elo"].to_numpy(), hf_home),
            self._design(d["away_elo"].to_numpy(), d["home_elo"].to_numpy(), hf_away),
        ])
        y = np.concatenate([d["home_score"].to_numpy(), d["away_score"].to_numpy()])
        sw = np.concatenate([w, w])
        self.glm = PoissonRegressor(alpha=self.alpha, max_iter=500)
        self.glm.fit(X, y, sample_weight=sw)
        self._fit_rho(d, w)
        return self

    def lambdas(self, elo_home, elo_away, neutral=True):
        lh = self.glm.predict(self._design([elo_home], [elo_away],
                                            [_home_field(neutral, True)]))[0]
        la = self.glm.predict(self._design([elo_away], [elo_home],
                                            [_home_field(neutral, False)]))[0]
        return float(lh), float(la)

    @staticmethod
    def _tau(i, j, lh, la, rho):
        if i == 0 and j == 0:
            return 1 - lh * la * rho
        if i == 0 and j == 1:
            return 1 + lh * rho
        if i == 1 and j == 0:
            return 1 + la * rho
        if i == 1 and j == 1:
            return 1 - rho
        return 1.0

    def grid(self, lh, la):
        ph = poisson.pmf(np.arange(MAXG + 1), lh)
        pa = poisson.pmf(np.arange(MAXG + 1), la)
        g = np.outer(ph, pa)
        r = self.rho
        for i in (0, 1):
            for j in (0, 1):
                g[i, j] *= self._tau(i, j, lh, la, r)
        return g / g.sum()

    def _fit_rho(self, d, w):
        lh = self.glm.predict(self._design(d["home_elo"].to_numpy(),
                                            d["away_elo"].to_numpy(),
                                            [_home_field(n, True) for n in d["neutral"]]))
        la = self.glm.predict(self._design(d["away_elo"].to_numpy(),
                                            d["home_elo"].to_numpy(),
                                            [_home_field(n, False) for n in d["neutral"]]))
        hs = d["home_score"].to_numpy().astype(int)
        as_ = d["away_score"].to_numpy().astype(int)
        low = (hs <= 1) & (as_ <= 1)  # rho only touches these cells

        def nll(rho):
            tau = np.array([self._tau(int(i), int(j), float(a), float(b), rho)
                            for i, j, a, b in zip(hs[low], as_[low], lh[low], la[low])])
            tau = np.clip(tau, 1e-9, None)
            return -np.sum(w[low] * np.log(tau))

        self.rho = float(minimize_scalar(nll, bounds=(-0.2, 0.2), method="bounded").x)

    def predict(self, elo_home, elo_away, neutral=True):
        lh, la = self.lambdas(elo_home, elo_away, neutral)
        g = self.grid(lh, la)
        p_home = float(np.tril(g, -1).sum())
        p_draw = float(np.trace(g))
        p_away = float(np.triu(g, 1).sum())
        i, j = np.unravel_index(np.argmax(g), g.shape)
        eh = float((g.sum(1) * np.arange(MAXG + 1)).sum())
        ea = float((g.sum(0) * np.arange(MAXG + 1)).sum())
        return {"probs": [p_home, p_draw, p_away],
                "lambda_home": lh, "lambda_away": la,
                "exp_home": eh, "exp_away": ea,
                "top_score": [int(i), int(j)],          # global modal exact score
                "proj_score": most_likely_score(g, int(np.argmax([p_home, p_draw, p_away]))),
                "grid": g}


if __name__ == "__main__":
    import data, elo
    df, ratings = elo.attach_elo(data.load_results())
    m = DixonColes().fit(df)
    strong, weak = ratings["Argentina"], ratings["New Zealand"]
    p = m.predict(strong, weak, neutral=True)
    print("Argentina vs New Zealand (neutral):", [round(x, 3) for x in p["probs"]],
          "lambda", round(p["lambda_home"], 2), round(p["lambda_away"], 2),
          "top", p["top_score"], "rho", round(m.rho, 3))
    assert abs(sum(p["probs"]) - 1) < 1e-6
    assert p["probs"][0] > p["probs"][2]          # strong side favoured
    assert p["lambda_home"] > p["lambda_away"]
    print("model OK")
