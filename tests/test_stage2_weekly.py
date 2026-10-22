"""Unit tests for src.stage2_weekly using synthetic inputs only."""

import numpy as np
import pandas as pd
import pytest

from src import airnow_hourly_series as ahs
from src import pm25_qc as qc
from src import stage2_weekly as s2


def _grid(values_by_hour, first_day="2021-03-01", n_days=1):
    labels = ahs.local_hour_ending_range(first_day, str((pd.Timestamp(first_day) + pd.Timedelta(days=n_days - 1)).date()))
    h = pd.DataFrame({"value": np.asarray(values_by_hour, dtype=float)}, index=labels[: len(values_by_hour)])
    h["valid"] = h["value"] >= 0
    return ahs.complete_grid(h, labels)


def _varied(n, start=10.0):
    return list(start + np.arange(n) * 1.5)


def test_seven_hour_run_is_excluded_before_daily_rule():
    # 17 varied hours + a 7-hour run -> 24 valid hours before the rule, 17 after -> incomplete
    vals = _varied(17) + [50.0] * 7
    daily, excluded = s2.final_daily(_grid(vals))
    assert excluded == 7
    assert daily["hours_valid"].tolist() == [17]
    assert daily["complete"].tolist() == [False]


def test_six_hour_run_is_kept():
    vals = _varied(18) + [50.0] * 6
    daily, excluded = s2.final_daily(_grid(vals))
    assert excluded == 0
    assert daily["hours_valid"].tolist() == [24] and daily["complete"].tolist() == [True]


def test_weekly_uses_six_of_seven_and_flags_smog_by_thursday():
    days = pd.date_range("2021-01-04", periods=14, freq="D", name="date")  # two Mon–Sun weeks
    hours = [24] * 6 + [10] + [24] * 5 + [10, 10]                      # week 1: 6 valid; week 2: 5 valid
    daily = pd.DataFrame({"hours_valid": hours, "pm25_daily_mean": np.arange(14) + 100.0}, index=days)
    w = s2.weekly_from_daily(daily)
    assert w["eligible_days"].tolist() == [6, 5]
    assert w["eligible"].tolist() == [True, False]
    assert w["complete_7_of_7"].tolist() == [False, False]
    assert w["smog_season_week"].tolist() == [True, True]
    assert w.loc[0, "weekly_mean_observed_days"] == pytest.approx(np.mean(np.arange(6) + 100.0))


def test_score_metrics():
    obs = pd.Series([10.0, 20.0, np.nan, 40.0])
    pred = pd.Series([12.0, 16.0, 5.0, np.nan])
    s = s2.score(obs, pred)
    assert s["n"] == 2
    assert s["mae"] == pytest.approx(3.0)
    assert s["rmse"] == pytest.approx(np.sqrt((4 + 16) / 2))
    assert s["bias"] == pytest.approx(-1.0)
    assert s2.score(pd.Series([np.nan]), pd.Series([1.0]))["n"] == 0


def test_score_table_only_uses_eligible_observed_weeks():
    preds = pd.DataFrame({
        "observed": [10.0, 99.0], "observed_eligible": [True, False],
        "persistence": [12.0, 0.0], "persistence_age_weeks": [1, 1],
        "climatology": [11.0, 0.0], "smog_season_week": [False, False],
    })
    t = s2.score_table(preds)
    assert t.loc["persistence_any_age", "n"] == 1
    assert t.loc["persistence_any_age", "mae"] == pytest.approx(2.0)
    assert t.loc["common_climatology", "mae"] == pytest.approx(1.0)
