"""Histogram gradient-boosting 1X2 challenger (sklearn, no libomp needed) and a
probability-averaging ensemble with the Dixon-Coles model.
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


class GBM:
    def __init__(self, **kw):
        self.clf = HistGradientBoostingClassifier(
            loss="log_loss", learning_rate=0.05, max_iter=300,
            max_leaf_nodes=31, min_samples_leaf=80, l2_regularization=1.0,
            early_stopping=True, validation_fraction=0.1, random_state=0, **kw)
        self.classes_ = [0, 1, 2]

    def fit(self, X, y):
        self.clf.fit(X, y.astype(int))
        self.classes_ = list(self.clf.classes_)
        return self

    def predict_proba(self, X):
        p = self.clf.predict_proba(X)
        # re-order to [Home, Draw, Away] regardless of class order seen in training
        out = np.zeros((len(X), 3))
        for k, c in enumerate(self.classes_):
            out[:, c] = p[:, k]
        return out / out.sum(1, keepdims=True)


def ensemble(*prob_arrays, weights=None):
    arrs = [np.asarray(p, float) for p in prob_arrays]
    if weights is None:
        weights = [1.0] * len(arrs)
    w = np.asarray(weights, float)
    stacked = np.tensordot(w, np.stack(arrs), axes=(0, 0)) / w.sum()
    return stacked / stacked.sum(1, keepdims=True)


if __name__ == "__main__":
    import data, elo, features, metrics
    df, _ = elo.attach_elo(data.load_results())
    X, y = features.build_features(df)
    m = np.isfinite(y)
    cut = int(m.sum() * 0.8)
    idx = np.where(m)[0]
    tr, te = idx[:cut], idx[cut:]
    g = GBM().fit(X.iloc[tr], y[tr])
    p = g.predict_proba(X.iloc[te])
    print("holdout GBM:", metrics.summary(p, y[te].astype(int)))
    assert abs(p.sum(1).mean() - 1) < 1e-6
    assert metrics.rps(p, y[te].astype(int)) < 0.23, "GBM worse than naive"
    print("gbm OK")
