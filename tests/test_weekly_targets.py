"""Unit tests for src.weekly_targets using small synthetic inputs (no real data)."""

import numpy as np
import pandas as pd
import pytest

from src import weekly_targets as wt

MONDAY = "2024-01-01"  # 2024-01-01 is a Monday


def _daily(dates, hours=24, means=10.0, **extra):
    dates = pd.to_datetime(pd.Series(dates)).dt.strftime("%Y-%m-%d")
    n = len(dates)
    hours = [hours] * n if np.isscalar(hours) else hours
    means = [means] * n if np.isscalar(means) else means
    return pd.DataFrame({"date": dates, "hours_valid": hours, "pm25_daily_mean": means, **extra})


def _week(start=MONDAY, n=7):
    return pd.date_range(start, periods=n, freq="D")


def _only_week(weekly, start=MONDAY):
    row = weekly.loc[weekly["week_start"] == pd.Timestamp(start)]
    assert len(row) == 1
    return row.iloc[0]


# --- input validation -------------------------------------------------------------------


def test_default_columns_match_processed_openaq_daily_header():
    assert (wt.DEFAULT_DATE_COL, wt.DEFAULT_MEAN_COL, wt.DEFAULT_HOURS_COL) == (
        "date",
        "pm25_daily_mean",
        "hours_valid",
    )
    assert wt.MIN_VALID_HOURS == 18


def test_duplicate_dates_raise_and_are_reported():
    d = _daily(["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-03"])
    with pytest.raises(ValueError, match="2024-01-02"):
        wt.build_weekly_targets(d, min_valid_days=7)


def test_non_parseable_date_raises():
    d = _daily(_week())
    d.loc[2, "date"] = "not-a-date"
    with pytest.raises(ValueError, match="non-parseable"):
        wt.daily_eligibility(d)


def test_missing_date_raises():
    d = _daily(_week())
    d.loc[2, "date"] = None
    with pytest.raises(ValueError, match="missing date"):
        wt.daily_eligibility(d)


def test_tz_aware_or_timed_dates_raise():
    d = _daily(_week())
    d["date"] = pd.date_range(MONDAY, periods=7, freq="D", tz="Asia/Karachi")
    with pytest.raises(ValueError, match="tz-naive"):
        wt.daily_eligibility(d)
    d = _daily(_week())
    d["date"] = pd.date_range("2024-01-01 05:00", periods=7, freq="D")
    with pytest.raises(ValueError, match="time of day"):
        wt.daily_eligibility(d)


@pytest.mark.parametrize("bad", [25, -1, np.nan, "x", 18.5])
def test_bad_hour_counts_raise(bad):
    d = _daily(_week())
    d["hours_valid"] = d["hours_valid"].astype(object)
    d.loc[3, "hours_valid"] = bad
    with pytest.raises(ValueError, match="hours_valid"):
        wt.daily_eligibility(d)


def test_missing_column_raises():
    d = _daily(_week()).drop(columns="hours_valid")
    with pytest.raises(ValueError, match="missing column"):
        wt.daily_eligibility(d)


def test_empty_input_raises():
    d = _daily([])
    with pytest.raises(ValueError, match="no rows"):
        wt.build_weekly_targets(d, min_valid_days=7)


# --- daily eligibility ------------------------------------------------------------------


def test_18_hour_boundary():
    d = _daily(_week(n=2), hours=[17, 18])
    days = wt.daily_eligibility(d)
    assert days["eligible"].tolist() == [False, True]
    assert days["reason"].tolist() == ["insufficient_hours", "ok"]


def test_upstream_complete_flag_is_ignored():
    d = _daily(_week(n=2), hours=[17, 24], complete=[True, False])
    days = wt.daily_eligibility(d)
    assert days["eligible"].tolist() == [False, True]


def test_nan_negative_non_numeric_means_are_invalid_and_counted_not_imputed():
    means = [10.0, np.nan, -5.0, "bad", np.inf, 20.0, 30.0]
    d = _daily(_week(), means=means)
    days = wt.daily_eligibility(d)
    assert days["valid_mean"].tolist() == [True, False, False, False, False, True, True]
    summary = wt.summarize_daily_validity(days)
    assert summary["invalid_mean_days"] == 4
    assert summary["eligible_days"] == 3

    row = _only_week(wt.build_weekly_targets(d, min_valid_days=5))
    assert row["eligible_days"] == 3
    assert row["ineligible_input_days"] == 4
    assert row["weekly_mean_observed_days"] == pytest.approx(20.0)  # mean(10, 20, 30)
    assert not row["eligible"]


def test_input_is_not_mutated_and_order_does_not_matter():
    d = _daily(_week(n=14), means=np.arange(14.0))
    before = d.copy()
    a = wt.build_weekly_targets(d, min_valid_days=7)
    b = wt.build_weekly_targets(d.sample(frac=1, random_state=0), min_valid_days=7)
    pd.testing.assert_frame_equal(d, before)
    pd.testing.assert_frame_equal(a, b)


# --- weekly aggregation -----------------------------------------------------------------


def test_full_week():
    d = _daily(_week(), means=[1, 2, 3, 4, 5, 6, 7])
    weekly = wt.build_weekly_targets(d, min_valid_days=7)
    assert list(weekly.columns) == wt.WEEKLY_COLUMNS
    row = _only_week(weekly)
    assert row["week_end"] == pd.Timestamp("2024-01-07")
    assert row["eligible_days"] == 7 and row["complete_7_of_7"] and row["eligible"]
    assert not row["partial_week"]
    assert row["weekly_mean_observed_days"] == pytest.approx(4.0)


def test_missing_calendar_days_count_as_missing_without_fill():
    dates = _week(n=14).delete([2, 9, 10])  # drop Wed of week 1, Wed+Thu of week 2
    d = _daily(dates, means=10.0)
    d.loc[d["date"] == "2024-01-02", "pm25_daily_mean"] = 40.0
    weekly = wt.build_weekly_targets(d, min_valid_days=6)
    w1, w2 = _only_week(weekly), _only_week(weekly, "2024-01-08")

    assert w1["days_in_input"] == 6 and w1["absent_days_in_record"] == 1
    assert w1["eligible_days"] == 6 and w1["missing_or_invalid_days"] == 1
    assert w1["weekly_mean_observed_days"] == pytest.approx((40 + 5 * 10) / 6)
    assert w1["eligible"] and not w1["complete_7_of_7"] and not w1["partial_week"]

    assert w2["eligible_days"] == 5 and w2["absent_days_in_record"] == 2
    assert not w2["eligible"]


def test_week_with_no_eligible_days_has_nan_mean():
    dates = _week(n=14)
    d = _daily(dates, hours=[24] * 7 + [10] * 7)
    row = _only_week(wt.build_weekly_targets(d, min_valid_days=5), "2024-01-08")
    assert row["eligible_days"] == 0
    assert np.isnan(row["weekly_mean_observed_days"])
    assert not row["eligible"]


@pytest.mark.parametrize("threshold, expected", [(5, True), (6, False), (7, False)])
def test_thresholds_with_five_eligible_days(threshold, expected):
    d = _daily(_week(), hours=[24, 24, 24, 24, 24, 17, 0])
    row = _only_week(wt.build_weekly_targets(d, min_valid_days=threshold))
    assert row["eligible_days"] == 5
    assert row["eligible"] == expected
    assert row["min_valid_days"] == threshold
    assert not row["complete_7_of_7"]


@pytest.mark.parametrize("threshold, expected", [(5, True), (6, True), (7, False)])
def test_thresholds_with_six_eligible_days(threshold, expected):
    d = _daily(_week(), hours=[24, 24, 24, 24, 24, 24, 3])
    row = _only_week(wt.build_weekly_targets(d, min_valid_days=threshold))
    assert row["eligible"] == expected


@pytest.mark.parametrize("bad", [0, 4, 8, 6.0, "6", True, None])
def test_invalid_threshold_rejected(bad):
    with pytest.raises(ValueError, match="min_valid_days"):
        wt.build_weekly_targets(_daily(_week()), min_valid_days=bad)


def test_threshold_is_required():
    with pytest.raises(TypeError):
        wt.build_weekly_targets(_daily(_week()))


def test_partial_weeks_at_record_edges():
    # Record runs Wednesday 2024-01-03 .. Tuesday 2024-01-16.
    d = _daily(pd.date_range("2024-01-03", "2024-01-16", freq="D"))
    weekly = wt.build_weekly_targets(d, min_valid_days=5)
    assert weekly["week_start"].tolist() == list(pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15"]))
    assert weekly["partial_week"].tolist() == [True, False, True]
    assert weekly["days_outside_record"].tolist() == [2, 0, 5]
    assert weekly["eligible_days"].tolist() == [5, 7, 2]
    assert weekly["eligible"].tolist() == [True, True, False]
    assert (weekly["week_start"].dt.dayofweek == 0).all()
    assert (weekly["week_end"].dt.dayofweek == 6).all()
