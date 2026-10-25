"""Synthetic-data tests for src.stage8_robustness (embargo timing, diagnostic shift, slope)."""

import numpy as np
import pandas as pd

from src import firms_features as ff
from src import mass_balance_features as mbf
from src import stage8_robustness as s8


def weekly_frame(n=80, start="2020-01-06"):
    ws = pd.date_range(start, periods=n, freq="7D")
    return pd.DataFrame({"week_start": ws, "week_end": ws + pd.Timedelta(days=6),
                         "weekly_mean_observed_days": np.arange(1, n + 1, dtype=float) * 10,
                         "eligible": True, "partial_week": False})


def test_history_features_embargo_uses_only_weeks_before_c():
    w = weekly_frame()
    t = w["week_start"].iloc[20]
    zero = s8.history_features(w, [t], 0).iloc[0]
    emb = s8.history_features(w, [t], 1).iloc[0]
    # zero embargo: last week is T-1 (value 200); embargo: last week is T-2 (value 190)
    assert np.isclose(np.exp(zero["log_last"]), 200.0) and zero["age_last"] == 1
    assert np.isclose(np.exp(emb["log_last"]), 190.0) and emb["age_last"] == 2
    # mean of the 4 weeks before C = T-7d: weeks T-2..T-5 -> 190, 180, 170, 160
    assert np.isclose(np.exp(emb["log_mean4"]), 175.0)
    # calendar terms are those of T in both cases
    assert np.isclose(zero["sin1"], emb["sin1"]) and np.isclose(zero["cos2"], emb["cos2"])


def test_baselines_embargo_persistence_skips_last_week():
    w = weekly_frame()
    t = w["week_start"].iloc[20]
    zero = s8.baselines(w, [t], 0).iloc[0]
    emb = s8.baselines(w, [t], 1).iloc[0]
    assert zero["persistence"] == 200.0 and emb["persistence"] == 190.0


def test_condition_shift_for_fire_and_box():
    days = pd.date_range("2021-01-04", periods=35, freq="D")
    fire = pd.DataFrame({"x_count": np.arange(35, dtype=float)}, index=days)
    t = pd.Timestamp("2021-01-25")                  # week T = days 21..27
    for lag, (lo, hi) in {1: (14, 20), 2: (7, 13), 0: (21, 27)}.items():
        got = ff.previous_week_features(fire, [t - (lag - 1) * s8.WEEK])["fire_prev_x_count"].iloc[0]
        assert got == sum(range(lo, hi + 1))
    hours = pd.date_range("2021-01-04", periods=35 * 24, freq="h")
    box = pd.DataFrame({"day": hours.normalize(), "vc": np.repeat(np.arange(35, dtype=float), 24),
                        "css_index": 1.0, "flush_hours": 1.0, "low_vent": False, "night": False})
    same = mbf.previous_week_features(box, [t + s8.WEEK])["mb_prev_vc_mean"].iloc[0]
    assert same == np.mean(np.arange(21, 28))      # weekly slope uses the target week's own hours


def test_traj_weekly_lag_mapping():
    dates = pd.date_range("2021-01-04", periods=21, freq="D")
    traj = pd.DataFrame({"date_pkt": dates, "traj_mean_dist72_km": np.arange(21, dtype=float),
                         "traj_frac_pts_east_se": 0.0, "traj_mean_height_m": 0.0})
    t = pd.Timestamp("2021-01-18")                  # third week
    assert s8.traj_weekly(traj, 0).loc[t, "traj_mean_dist72_km"] == np.mean(range(14, 21))
    assert s8.traj_weekly(traj, 1).loc[t, "traj_mean_dist72_km"] == np.mean(range(7, 14))
    assert s8.traj_weekly(traj, 2).loc[t, "traj_mean_dist72_km"] == np.mean(range(0, 7))


def test_rf_training_rows_end_before_embargo_cutoff():
    w = weekly_frame(n=60)
    table = w.rename(columns={"week_start": "target_week_start"}).copy()
    table["f"] = np.arange(60, dtype=float)
    # the week just before the target has a huge target value; with embargo it must not be trained on
    t_idx = 55
    table.loc[t_idx - 1, "weekly_mean_observed_days"] = 1e6
    t = table["target_week_start"].iloc[t_idx]
    zero = s8.walk_forward_rf(table, ["f"], [t], 0)["pred"].iloc[0]
    emb = s8.walk_forward_rf(table, ["f"], [t], 1)["pred"].iloc[0]
    assert emb < 1e3 < zero


def test_ols_slope_and_bootstrap_recover_known_slope():
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    y = 2.0 - 1.0 * x + rng.normal(scale=0.1, size=200)
    assert abs(s8.ols_slope(x, y) + 1.0) < 0.05
    lo, hi = s8.block_bootstrap_slope(x, y)
    assert lo < -1.0 < hi and hi - lo < 0.2
