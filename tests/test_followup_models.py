"""Unit tests for src.followup_models using synthetic data only."""

import numpy as np
import pandas as pd
import pytest

from src import followup_models as fm

FAST_RF = {"n_estimators": 40, "min_samples_leaf": 2, "max_features": 1.0, "random_state": 0, "n_jobs": 1,
           "oob_score": True}


def _table(n=120, seed=1):
    rng = np.random.default_rng(seed)
    ws = pd.date_range("2019-01-07", periods=n, freq="7D")
    x = rng.normal(size=n)
    fire = rng.gamma(0.5, 400, size=n)
    y = np.exp(4.5 + 0.4 * x + rng.normal(scale=0.05, size=n))
    return pd.DataFrame({"target_week_start": ws, "week_end": ws + pd.Timedelta(days=6),
                         "weekly_mean_observed_days": y, "eligible": True, "partial_week": False,
                         "x": x, "fire_prev_r0_100_count": fire})


def test_log1p_fire_only_touches_fire_columns():
    X = pd.DataFrame({"x": [-1.0, 2.0], "fire_prev_a": [0.0, np.e - 1]})
    out = fm.log1p_fire(X)
    assert out["x"].tolist() == [-1.0, 2.0]
    assert out["fire_prev_a"].tolist() == pytest.approx([0.0, 1.0])
    assert X["fire_prev_a"].tolist() == [0.0, np.e - 1]            # input not modified


@pytest.mark.parametrize("kind", ["rflog", "ridgeall"])
def test_walk_forward_is_leak_free_positive_and_deterministic(kind):
    t = _table()
    feats = ["x", "fire_prev_r0_100_count"]
    tgt = t["target_week_start"].iloc[[100]]
    p1 = fm.walk_forward(t, feats, tgt, kind, rf_params=FAST_RF, min_train=52)
    t2 = t.copy()
    t2.loc[100:, "weekly_mean_observed_days"] = 1e6
    t2.loc[101:, feats] = 999.0
    p2 = fm.walk_forward(t2, feats, tgt, kind, rf_params=FAST_RF, min_train=52)
    p3 = fm.walk_forward(t, feats, tgt, kind, rf_params=FAST_RF, min_train=52)
    assert p1.loc[0, "reason"] == "ok" and p1.loc[0, "pred"] > 0
    assert p1.loc[0, "pred"] == pytest.approx(p2.loc[0, "pred"])
    assert p1.loc[0, "pred"] == pytest.approx(p3.loc[0, "pred"])


def test_ridgeall_recovers_a_log_linear_relationship():
    t = _table(n=200)
    p = fm.walk_forward(t, ["x"], t["target_week_start"].iloc[[180, 190]], "ridgeall", min_train=52)
    truth = t.set_index("target_week_start").loc[p["target_week_start"], "weekly_mean_observed_days"].to_numpy()
    assert np.allclose(p["pred"].to_numpy(), truth, rtol=0.1)


def test_unknown_kind_raises():
    t = _table()
    with pytest.raises(ValueError):
        fm.walk_forward(t, ["x"], t["target_week_start"].iloc[[100]], "something", min_train=52)
