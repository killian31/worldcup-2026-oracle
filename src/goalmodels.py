"""Goal-model variants for the exact-score bake-off (see goalbench.py).

Two levers the production Elo->Poisson Dixon-Coles can't pull, each aimed at
*scoreline* quality rather than 1X2:

  1. Negative-Binomial marginals (`negbin=True`) — goals are modelled with a
     fitted dispersion `r` instead of fixed Poisson variance=mean. Captures the
     fat tail (4-3, 7-1) if football is actually overdispersed.

  2. Team attack/defence (`attack_defence=True`) — a single Elo number collapses
     a team's scoring and conceding into one. Here each team gets a small
     attack/defence *correction* on top of the Elo baseline, fit by a ridge-
     penalised Poisson GLM with an offset (the penalty shrinks corrections toward
     0 unless a team has earned the deviation — essential for sparse national-team
     data). This is what lets "Japan score even when they lose" be expressible.

GoalModel() with both flags off is byte-for-byte the production DixonColes, so the
baseline row of the bake-off is the real current model.
"""
import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import gammaln
from scipy.stats import nbinom

from model import MAXG, DixonColes, _home_field, _round_half_up


def _fit_attack_defence(n_teams, s_idx, c_idx, offset, y, w, lam):
    """Ridge-penalised Poisson GLM with offset: log mu = offset + att[s] + def[c].
    Returns (att, def) arrays, each length n_teams, shrunk toward 0 by `lam`."""
    def obj(theta):
        att, dfc = theta[:n_teams], theta[n_teams:]
        eta = offset + att[s_idx] + dfc[c_idx]
        mu = np.exp(eta)
        nll = float(np.sum(w * (mu - y * eta)))                 # Poisson NLL (drop const)
        resid = w * (mu - y)                                    # dNLL/deta per row
        g_att = np.bincount(s_idx, weights=resid, minlength=n_teams)
        g_def = np.bincount(c_idx, weights=resid, minlength=n_teams)
        nll += lam * float(att @ att + dfc @ dfc)
        g_att += 2 * lam * att
        g_def += 2 * lam * dfc
        return nll, np.concatenate([g_att, g_def])

    res = minimize(obj, np.zeros(2 * n_teams), jac=True, method="L-BFGS-B",
                   options={"maxiter": 300})
    return res.x[:n_teams], res.x[n_teams:]


class GoalModel(DixonColes):
    def __init__(self, xi=None, alpha=1e-4, attack_defence=False, negbin=False, ad_lambda=50.0):
        super().__init__(**({} if xi is None else {"xi": xi}), alpha=alpha)
        self.attack_defence = attack_defence
        self.negbin = negbin
        self.ad_lambda = ad_lambda
        self.att, self.dfc = {}, {}
        self.r = None  # NegBin size; None => Poisson

    # --- baseline (Elo) expected goals for the played matches, both perspectives ---
    def _baseline_lambdas(self, d):
        hf_h = [_home_field(n, True) for n in d["neutral"]]
        hf_a = [_home_field(n, False) for n in d["neutral"]]
        lh = self.glm.predict(self._design(d["home_elo"].to_numpy(), d["away_elo"].to_numpy(), hf_h))
        la = self.glm.predict(self._design(d["away_elo"].to_numpy(), d["home_elo"].to_numpy(), hf_a))
        return lh, la

    def _team_vec(self, names, table):
        return np.array([table.get(t, 0.0) for t in names])

    def _adjust(self, d, lh, la):
        ah, dh = self._team_vec(d["home_team"], self.att), self._team_vec(d["home_team"], self.dfc)
        aa, da = self._team_vec(d["away_team"], self.att), self._team_vec(d["away_team"], self.dfc)
        return lh * np.exp(ah + da), la * np.exp(aa + dh)

    def fit(self, df):
        super().fit(df)                       # self.glm (Elo->goals) + self.rho
        d = df[df["played"]].copy()
        w = np.exp(-self.xi * (d["date"].max() - d["date"]).dt.days.to_numpy())
        lh, la = self._baseline_lambdas(d)
        if self.attack_defence:
            teams = sorted(set(d["home_team"]) | set(d["away_team"]))
            idx = {t: k for k, t in enumerate(teams)}
            home = d["home_team"].map(idx).to_numpy()
            away = d["away_team"].map(idx).to_numpy()
            s_idx = np.concatenate([home, away])           # scorer
            c_idx = np.concatenate([away, home])           # conceder
            offset = np.log(np.concatenate([lh, la]))
            y = np.concatenate([d["home_score"].to_numpy(), d["away_score"].to_numpy()]).astype(float)
            att, dfc = _fit_attack_defence(len(teams), s_idx, c_idx, offset, y,
                                           np.concatenate([w, w]), self.ad_lambda)
            self.att = {t: float(att[k]) for t, k in idx.items()}
            self.dfc = {t: float(dfc[k]) for t, k in idx.items()}
            lh, la = self._adjust(d, lh, la)
        if self.negbin:
            mu = np.concatenate([lh, la])
            y = np.concatenate([d["home_score"].to_numpy(), d["away_score"].to_numpy()]).astype(float)
            ww = np.concatenate([w, w])

            def nll(logr):
                r = np.exp(logr)
                ll = (gammaln(y + r) - gammaln(r) - gammaln(y + 1)
                      + r * np.log(r / (r + mu)) + y * np.log(mu / (r + mu)))
                return -float(np.sum(ww * ll))

            res = minimize_scalar(nll, bounds=(np.log(1.0), np.log(500.0)), method="bounded")
            self.r = float(np.exp(res.x))
        return self

    def grid(self, lh, la):
        if self.r is None:
            return super().grid(lh, la)
        k = np.arange(MAXG + 1)
        ph = nbinom.pmf(k, self.r, self.r / (self.r + lh))
        pa = nbinom.pmf(k, self.r, self.r / (self.r + la))
        g = np.outer(ph, pa)
        for i in (0, 1):
            for j in (0, 1):
                g[i, j] *= self._tau(i, j, lh, la, self.rho)
        return g / g.sum()

    def predict(self, elo_home, elo_away, neutral=True, home_team=None, away_team=None):
        lh, la = self.lambdas(elo_home, elo_away, neutral)
        if self.attack_defence and home_team is not None:
            lh *= np.exp(self.att.get(home_team, 0.0) + self.dfc.get(away_team, 0.0))
            la *= np.exp(self.att.get(away_team, 0.0) + self.dfc.get(home_team, 0.0))
        g = self.grid(lh, la)
        ph = float(np.tril(g, -1).sum()); pd_ = float(np.trace(g)); pa = float(np.triu(g, 1).sum())
        i, j = np.unravel_index(np.argmax(g), g.shape)
        eh = float((g.sum(1) * np.arange(MAXG + 1)).sum())
        ea = float((g.sum(0) * np.arange(MAXG + 1)).sum())
        return {"probs": [ph, pd_, pa], "exp_home": eh, "exp_away": ea,
                "top_score": [int(i), int(j)], "grid": g}


if __name__ == "__main__":
    import data
    import elo
    df, ratings = elo.attach_elo(data.load_results())

    base = GoalModel().fit(df)                                   # == production DixonColes
    nb = GoalModel(negbin=True).fit(df)
    ad = GoalModel(attack_defence=True).fit(df)

    eh = ratings["Brazil"]; ea = ratings["Japan"]
    for name, m in [("base", base), ("negbin", nb), ("attdef", ad)]:
        p = m.predict(eh, ea, neutral=True, home_team="Brazil", away_team="Japan")
        assert abs(sum(p["probs"]) - 1) < 1e-6
        print(f"{name:7} Brazil-Japan {[round(x,3) for x in p['probs']]} "
              f"E[g] {p['exp_home']:.2f}-{p['exp_away']:.2f}")

    # NegBin must put MORE mass on high-scoring games than Poisson at the same mean
    assert nb.r and nb.r < 500
    p_tot = lambda g: float(g[np.add.outer(np.arange(MAXG+1), np.arange(MAXG+1)) >= 5].sum())
    gp = base.grid(1.6, 1.4); gn = nb.grid(1.6, 1.4)
    assert p_tot(gn) > p_tot(gp), "NegBin should fatten the high-total tail"
    print(f"P(total>=5 goals)  poisson {p_tot(gp):.3f}  negbin {p_tot(gn):.3f}  (r={nb.r:.1f})")

    # attack/defence: corrections exist and are shrunk small; print a few extremes
    items = sorted(ad.att.items(), key=lambda kv: -kv[1])
    assert max(abs(v) for v in ad.att.values()) < 1.0, "ridge should keep corrections modest"
    print("top attack corrections:", [(t, round(v, 2)) for t, v in items[:5]])
    print("goalmodels OK")
