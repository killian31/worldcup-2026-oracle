"""Scoring rules for 1X2 forecasts. Probabilities are ordered [Home, Draw, Away];
outcomes are integer class ids 0=Home, 1=Draw, 2=Away.

RPS (Ranked Probability Score) is the primary metric — it is distance-sensitive,
so predicting Home when the result is Away is penalised more than predicting Home
when it's a Draw. Lower is better.
"""
import numpy as np

H, D, A = 0, 1, 2


def _onehot(outcomes):
    o = np.zeros((len(outcomes), 3))
    o[np.arange(len(outcomes)), np.asarray(outcomes, int)] = 1.0
    return o


def rps(probs, outcomes):
    p = np.asarray(probs, float)
    o = _onehot(outcomes)
    cp, co = np.cumsum(p, axis=1), np.cumsum(o, axis=1)
    # sum over first r-1 = 2 boundaries, normalised by (r-1)=2
    return float(np.mean(np.sum((cp[:, :2] - co[:, :2]) ** 2, axis=1) / 2.0))


def log_loss(probs, outcomes, eps=1e-15):
    p = np.clip(np.asarray(probs, float), eps, 1)
    idx = np.asarray(outcomes, int)
    return float(np.mean(-np.log(p[np.arange(len(idx)), idx])))


def brier(probs, outcomes):
    p = np.asarray(probs, float)
    return float(np.mean(np.sum((p - _onehot(outcomes)) ** 2, axis=1)))


def accuracy(probs, outcomes):
    return float(np.mean(np.argmax(np.asarray(probs), axis=1) == np.asarray(outcomes, int)))


def ece(probs, outcomes, bins=10):
    """Top-label expected calibration error."""
    p = np.asarray(probs, float)
    conf = p.max(axis=1)
    pred = p.argmax(axis=1)
    correct = (pred == np.asarray(outcomes, int)).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    e, n = 0.0, len(p)
    for i in range(bins):
        m = (conf > edges[i]) & (conf <= edges[i + 1])
        if m.sum():
            e += m.sum() / n * abs(correct[m].mean() - conf[m].mean())
    return float(e)


def outcome_of(home_goals, away_goals):
    return H if home_goals > away_goals else (D if home_goals == away_goals else A)


def summary(probs, outcomes):
    return {"rps": round(rps(probs, outcomes), 4),
            "log_loss": round(log_loss(probs, outcomes), 4),
            "brier": round(brier(probs, outcomes), 4),
            "accuracy": round(accuracy(probs, outcomes), 4),
            "ece": round(ece(probs, outcomes), 4),
            "n": len(outcomes)}


if __name__ == "__main__":
    # perfect forecast -> 0 ; a known hand-calc check for RPS
    assert rps([[1, 0, 0]], [H]) == 0.0
    # p=[.5,.3,.2], outcome Home: cum p=[.5,.8], cum o=[1,1] -> (.25+.04)/2=.145
    assert abs(rps([[.5, .3, .2]], [H]) - 0.145) < 1e-9
    # uniform forecast RPS = (( .333)^2 + (.333)^2 )/2 ~ 0.1111 for a Home result
    assert abs(rps([[1 / 3, 1 / 3, 1 / 3]], [H]) - ((1 - 1 / 3) ** 2 + (1 - 2 / 3) ** 2) / 2) < 1e-9
    print("metrics OK")
