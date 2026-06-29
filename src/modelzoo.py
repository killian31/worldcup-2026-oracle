"""Model zoo — train many diverse models on the SAME walk-forward split and
compare honestly. Answers: can a neural net / mixture-of-experts / stacked router
beat the Elo->Dixon-Coles + gradient-boosting ensemble?

Bases:  elo-logistic, Dixon-Coles, HistGBM, MLP (torch/MPS),
        confederation mixture-of-experts, ens(DC+GBM).
On top: a stacked ROUTER (meta-learner over the base probabilities + elo gap) —
        the "train one on top that routes to the best" idea, evaluated on a
        held-out temporal slice. Also reports an in-hindsight ORACLE upper bound
        and the error-correlation between models (are they actually orthogonal?).

Primary metric RPS (lower better). Honest by construction: every model sees the
identical rolling-origin folds; the router/leaderboard are scored on a held-out
tail none of them tuned on.
"""
import json
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

import data
import elo
import features as featlib
import gbm as gbmlib
import metrics
import teams
from model import DixonColes

warnings.filterwarnings("ignore")
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "modelzoo.json")
LABEL = {"ROUTER(stacked)": "Stacked router", "ens_dc_gbm": "Ensemble (DC + GBM)",
         "dixon_coles": "Dixon-Coles", "gbm": "Gradient boosting", "elo_logistic": "Elo logistic",
         "moe_conf": "Mixture of experts", "mlp": "Neural net (MLP)"}
CONFS = ["UEFA", "CONMEBOL", "CONCACAF", "CAF", "AFC", "OFC"]


# ---------- individual model trainers (return P[H,D,A] for the test block) ----------
def m_elo_logistic(df_tr, X_tr, y_tr, df_te, X_te):
    clf = LogisticRegression(max_iter=300, C=1.0)
    clf.fit(X_tr[["elo_diff"]], y_tr)
    return _reorder(clf, clf.predict_proba(X_te[["elo_diff"]]))


def m_gbm(df_tr, X_tr, y_tr, df_te, X_te):
    g = gbmlib.GBM().fit(X_tr, y_tr)
    return g.predict_proba(X_te)


def m_dc(df_tr, X_tr, y_tr, df_te, X_te):
    dc = DixonColes().fit(df_tr)
    return np.array([dc.predict(r.home_elo, r.away_elo, bool(r.neutral))["probs"]
                     for r in df_te.itertuples()])


def m_moe_conf(df_tr, X_tr, y_tr, df_te, X_te):
    """Hard-gated mixture of experts: one HistGBM per home-confederation, with a
    global model as fallback when an expert has too little data."""
    glob = gbmlib.GBM().fit(X_tr, y_tr)
    conf_tr = df_tr["home_team"].map(teams.confederation).to_numpy()
    experts = {}
    for c in CONFS:
        mask = conf_tr == c
        if mask.sum() >= 1500:
            experts[c] = gbmlib.GBM().fit(X_tr[mask], y_tr[mask])
    out = glob.predict_proba(X_te)
    conf_te = df_te["home_team"].map(teams.confederation).to_numpy()
    for c, ex in experts.items():
        m = conf_te == c
        if m.any():
            out[m] = ex.predict_proba(X_te[m])
    return out


def m_mlp(df_tr, X_tr, y_tr, df_te, X_te):
    import torch
    import torch.nn as nn
    torch.manual_seed(0)
    dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    mu, sd = X_tr.mean(), X_tr.std().replace(0, 1)
    Xtr = torch.tensor(((X_tr - mu) / sd).to_numpy(), dtype=torch.float32, device=dev)
    Xte = torch.tensor(((X_te - mu) / sd).to_numpy(), dtype=torch.float32, device=dev)
    ytr = torch.tensor(y_tr.astype(int), dtype=torch.long, device=dev)
    net = nn.Sequential(nn.Linear(X_tr.shape[1], 64), nn.ReLU(), nn.Dropout(0.3),
                        nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3), nn.Linear(32, 3)).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss(label_smoothing=0.05)
    net.train()
    for _ in range(120):
        opt.zero_grad()
        loss = lossf(net(Xtr), ytr)
        loss.backward(); opt.step()
    net.eval()
    with torch.no_grad():
        p = torch.softmax(net(Xte), dim=1).cpu().numpy()
    return p / p.sum(1, keepdims=True)


def _reorder(clf, p):
    out = np.zeros((p.shape[0], 3))
    for k, c in enumerate(clf.classes_):
        out[:, int(c)] = p[:, k]
    return out / out.sum(1, keepdims=True)


BASES = {"elo_logistic": m_elo_logistic, "dixon_coles": m_dc, "gbm": m_gbm,
         "moe_conf": m_moe_conf, "mlp": m_mlp}


def walk(df, X, y, years=3, retrain_days=120):
    played = df["played"].to_numpy()
    dates = df["date"]
    end = dates.max(); start = end - pd.Timedelta(days=int(365.25 * years))
    edges = pd.date_range(start, end + pd.Timedelta(days=retrain_days), freq=f"{retrain_days}D")
    rows = {k: [] for k in BASES}
    outs, elo_gap, dts = [], [], []
    nblocks = 0
    for b0, b1 in zip(edges[:-1], edges[1:]):
        te = played & (dates >= b0).to_numpy() & (dates < b1).to_numpy()
        tr = played & (dates < b0).to_numpy()
        if te.sum() == 0 or tr.sum() < 2500:
            continue
        tri, tei = np.where(tr)[0], np.where(te)[0]
        df_tr, df_te = df.iloc[tri], df.iloc[tei]
        Xtr, Xte = X.iloc[tri], X.iloc[tei]
        ytr = y[tri]
        for name, fn in BASES.items():
            try:
                rows[name].append(fn(df_tr, Xtr, ytr, df_te, Xte))
            except Exception as e:
                print(f"  {name} failed on a block: {e}")
                rows[name].append(np.full((len(tei), 3), 1 / 3))
        outs.append(y[tei].astype(int))
        elo_gap.append(Xte["elo_diff"].to_numpy())
        dts.append(df_te["date"].to_numpy())
        nblocks += 1
        print(f"  block {nblocks}: train {len(tri)}, test {len(tei)}")
    P = {k: np.vstack(v) for k, v in rows.items()}
    return P, np.concatenate(outs), np.concatenate(elo_gap), np.concatenate(dts)


def main():
    df, _ = elo.attach_elo(data.load_results())
    X, y = featlib.build_features(df)
    print("running walk-forward over the model zoo...")
    P, out, gap, dts = walk(df, X, y)
    n = len(out)
    order = np.argsort(dts)
    P = {k: v[order] for k, v in P.items()}
    out, gap = out[order], gap[order]
    # add the existing production ensemble
    P["ens_dc_gbm"] = gbmlib.ensemble(P["dixon_coles"], P["gbm"], weights=[0.6, 0.4])

    split = int(n * 0.6)
    names = list(P)
    print(f"\ntotal test matches {n}; meta-train {split}, held-out eval {n - split}\n")

    # stacked ROUTER: meta-logistic over base probs (+ elo gap) on the eval tail
    base_for_meta = ["elo_logistic", "dixon_coles", "gbm", "moe_conf", "mlp"]
    Z = np.hstack([P[k] for k in base_for_meta] + [gap.reshape(-1, 1)])
    meta = LogisticRegression(max_iter=500, C=0.5)
    meta.fit(Z[:split], out[:split])
    router = _reorder(meta, meta.predict_proba(Z[split:]))

    # leaderboard on the SAME held-out tail
    ev = slice(split, n)
    board = {}
    for k in names:
        board[k] = metrics.summary(P[k][ev], out[ev])
    board["ROUTER(stacked)"] = metrics.summary(router, out[ev])
    # oracle upper bound: pick, per match, the base that gave the truth highest prob
    stack = np.stack([P[k][ev] for k in base_for_meta])  # (M, n_eval, 3)
    truth_p = stack[:, np.arange(stack.shape[1]), out[ev]]   # (M, n_eval)
    best = truth_p.argmax(0)
    oracle = stack[best, np.arange(stack.shape[1])]
    board["ORACLE(hindsight)"] = metrics.summary(oracle, out[ev])

    print(f"{'model':<20}{'RPS':>8}{'logloss':>9}{'acc':>7}{'ECE':>7}")
    for k, s in sorted(board.items(), key=lambda kv: kv[1]["rps"]):
        print(f"{k:<20}{s['rps']:>8.4f}{s['log_loss']:>9.4f}{s['accuracy']:>7.3f}{s['ece']:>7.3f}")

    # complementarity: correlation of per-match log-loss between base models
    print("\nper-match log-loss correlation (lower = more orthogonal/complementary):")
    eps = 1e-9
    ll = {k: -np.log(np.clip(P[k][ev][np.arange(n - split), out[ev]], eps, 1)) for k in base_for_meta}
    print("           " + "".join(f"{k[:7]:>9}" for k in base_for_meta))
    corrs = []
    for a in base_for_meta:
        print(f"{a[:10]:<11}" + "".join(f"{np.corrcoef(ll[a], ll[b])[0,1]:>9.2f}" for b in base_for_meta))
        corrs += [np.corrcoef(ll[a], ll[b])[0, 1] for b in base_for_meta if b != a]

    # display-friendly leaderboard for the app (exclude the hindsight oracle)
    lb = [{"model": LABEL.get(k, k), "rps": s["rps"], "acc": s["accuracy"], "ece": s["ece"],
           "note": "current production model" if k == "ens_dc_gbm" else ""}
          for k, s in sorted(board.items(), key=lambda kv: kv[1]["rps"]) if k != "ORACLE(hindsight)"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"n_eval": n - split, "oracle_rps": board["ORACLE(hindsight)"]["rps"],
               "avg_error_corr": round(float(np.mean(corrs)), 2), "leaderboard": lb},
              open(OUT, "w"), indent=2)
    print(f"\nbest: {lb[0]['model']}  ->  wrote {OUT}")


if __name__ == "__main__":
    main()
