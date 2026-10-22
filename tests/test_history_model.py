"""Unit tests for src.history_model using synthetic weekly series only."""

import numpy as np
import pandas as pd
import pytest

from src import history_model as hm


def _weekly(values, start="2019-01-07", eligible=None):
    ws = pd.date_range(start, periods=len(values), freq="7D")
    return pd.DataFrame({
        "week_start": ws, "week_end": ws + pd.Timedelta(days=6),
        "weekly_mean_observed_days": np.asarray(values, dtype=float),
        "eligible": np.ones(len(values), bool) if eligible is None else np.asarray(eligible, bool),
    })


def _seasonal(n=160):
    t = np.arange(n)
    return 100 + 60 * np.sin(2 * np.pi * t / 52.18) + 10 * np.cos(2 * np.pi * t / 7.3)


def test_features_use_only_weeks_before_cutoff():
    w = _weekly(_seasonal())
    t = w["week_start"].iloc[100]
    f1 = hm.features_for_targets(w, [t]).iloc[0]
    w2 = w.copy()
    w2.loc[100:, "weekly_mean_observed_days"] = 9999.0   # change the target week and everything after
    f2 = hm.features_for_targets(w2, [t]).iloc[0]
    assert f1["log_last"] == pytest.approx(np.log(w.loc[99, "weekly_mean_observed_days"]))
    assert f1[hm.FEATURES].equals(f2[hm.FEATURES])


def test_ineligible_weeks_skipped_and_no_prediction_without_recent_data():
    vals = _seasonal(20)
    elig = np.ones(20, bool)
    elig[15:19] = False                                       # weeks T-4..T-1 of target 19 ineligible
    w = _weekly(vals, eligible=elig)
    f = hm.features_for_targets(w, [w["week_start"].iloc[19], w["week_start"].iloc[16]])
    assert f.loc[0, "reason"] == "no_eligible_week_in_lookback" and np.isnan(f.loc[0, "log_last"])
    assert f.loc[1, "reason"] == "ok" and f.loc[1, "age_last"] == 2  # week 14 used for target 16


def test_walk_forward_is_leak_free_and_needs_minimum_training():
    w = _weekly(_seasonal())
    targets = w["week_start"].iloc[[30, 120]]
    p1 = hm.walk_forward(w, targets).set_index("target_week_start")
    assert p1.loc[targets.iloc[0], "history_reason"] == "too_little_training_data"
    assert p1.loc[targets.iloc[1], "history_reason"] == "ok"
    w2 = w.copy()
    w2.loc[120:, "weekly_mean_observed_days"] *= 5             # future and target change
    p2 = hm.walk_forward(w2, targets).set_index("target_week_start")
    assert p1.loc[targets.iloc[1], "history_model"] == pytest.approx(p2.loc[targets.iloc[1], "history_model"])


def test_constant_series_predicts_the_constant():
    w = _weekly(np.full(120, 80.0))
    p = hm.walk_forward(w, [w["week_start"].iloc[110]])
    assert p.loc[0, "history_model"] == pytest.approx(80.0, rel=1e-6)


def test_comparison_scores_uses_common_eligible_set():
    preds = pd.DataFrame({
        "observed": [10.0, 20.0, 30.0], "observed_eligible": [True, True, False],
        "persistence": [12.0, 18.0, 0.0], "climatology": [10.0, np.nan, 0.0], "history_model": [11.0, 20.0, 0.0],
        "smog_season_week": [False, True, False],
    })
    s = hm.comparison_scores(preds)
    assert s.loc[("all", "history_model"), "n"] == 1          # only week 0 has all three and is eligible
    assert s.loc[("all", "persistence"), "mae"] == pytest.approx(2.0)
