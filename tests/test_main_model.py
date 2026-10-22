"""Unit tests for src.main_model using synthetic data only."""

import numpy as np
import pandas as pd
import pytest

from src import main_model as mm

FAST = {"n_estimators": 20, "min_samples_leaf": 2, "max_features": 1.0, "random_state": 0, "n_jobs": 1}


def _table(n=120, seed=0):
    rng = np.random.default_rng(seed)
    ws = pd.date_range("2019-01-07", periods=n, freq="7D")
    x = rng.normal(size=n)
    y = 100 + 30 * x + rng.normal(scale=2, size=n)
    return pd.DataFrame({"target_week_start": ws, "week_end": ws + pd.Timedelta(days=6),
                         "weekly_mean_observed_days": y, "eligible": True, "partial_week": False,
                         "x": x, "noise": rng.normal(size=n)})


def test_walk_forward_rf_is_leak_free_and_deterministic():
    t = _table()
    tgt = t["target_week_start"].iloc[[100]]
    p1 = mm.walk_forward_rf(t, ["x", "noise"], tgt, params=FAST, min_train=52)
    t2 = t.copy()
    t2.loc[100:, "weekly_mean_observed_days"] = 1e6          # target week and later change
    t2.loc[101:, ["x", "noise"]] = 999.0                       # later features change
    p2 = mm.walk_forward_rf(t2, ["x", "noise"], tgt, params=FAST, min_train=52)
    assert p1.loc[0, "reason"] == "ok" and p1.loc[0, "n_train"] == 100
    assert p1.loc[0, "pred"] == pytest.approx(p2.loc[0, "pred"])
    p3 = mm.walk_forward_rf(t, ["x", "noise"], tgt, params=FAST, min_train=52)
    assert p1.loc[0, "pred"] == pytest.approx(p3.loc[0, "pred"])   # fixed seed -> same result


def test_walk_forward_rf_skips_ineligible_training_rows_and_missing_features():
    t = _table()
    t.loc[:59, "eligible"] = False
    t.loc[110, "x"] = np.nan
    p = mm.walk_forward_rf(t, ["x"], t["target_week_start"].iloc[[100, 110]], params=FAST, min_train=52)
    assert p.loc[0, "reason"] == "too_little_training_data" and p.loc[0, "n_train"] == 40
    assert p.loc[1, "reason"] == "missing_features" and np.isnan(p.loc[1, "pred"])


def test_block_bootstrap_sign_and_determinism():
    a = np.full(60, 1.0)      # model a always 1 off
    b = np.full(60, 3.0)      # model b always 3 off
    r1 = mm.block_bootstrap_mae_diff(a, b, n_boot=200)
    r2 = mm.block_bootstrap_mae_diff(a, b, n_boot=200)
    assert r1["mae_diff"] == pytest.approx(-2.0)
    assert r1["ci95_low"] == pytest.approx(-2.0) and r1["ci95_high"] == pytest.approx(-2.0)
    assert r1 == r2


def test_score_all_uses_common_eligible_set():
    preds = pd.DataFrame({"observed": [10.0, 20.0, 30.0], "observed_eligible": [True, True, False],
                          "smog_season_week": [False, True, False],
                          "a": [12.0, 18.0, 0.0], "b": [10.0, np.nan, 0.0]})
    s = mm.score_all(preds, ["a", "b"])
    assert s.loc[("all", "a"), "n"] == 1 and s.loc[("all", "a"), "mae"] == pytest.approx(2.0)
    assert s.loc[("all", "b"), "mae"] == pytest.approx(0.0)
