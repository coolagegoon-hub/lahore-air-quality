"""Unit tests for src.baselines using small synthetic weekly frames (no real data)."""

import numpy as np
import pandas as pd
import pytest

from src import baselines as bl
from src import weekly_targets as wt


def _weekly(start, n, means=None, eligible=True):
    starts = pd.date_range(start, periods=n, freq="7D")
    assert (starts.day_of_week == 0).all()
    means = np.arange(n, dtype=float) if means is None else np.asarray(means, dtype=float)
    elig = np.full(n, eligible) if np.isscalar(eligible) else np.asarray(eligible, dtype=bool)
    return pd.DataFrame(
        {
            "week_start": starts,
            "week_end": starts + pd.Timedelta(days=6),
            "weekly_mean_observed_days": means,
            "eligible": elig,
        }
    )


def _set(weekly, week_start, **values):
    w = weekly.copy()
    mask = w["week_start"] == pd.Timestamp(week_start)
    assert mask.sum() == 1
    for k, v in values.items():
        w.loc[mask, k] = v
    return w


CLIM = dict(window_weeks=2, min_years=2, min_samples=5)


# --- cutoff -----------------------------------------------------------------------------


def test_cutoff_requires_monday_midnight():
    assert bl.issuance_cutoff("2024-01-08") == pd.Timestamp("2024-01-08")
    for bad in ["2024-01-09", "2024-01-08 06:00"]:
        with pytest.raises(ValueError, match="Monday"):
            bl.issuance_cutoff(bad)
    with pytest.raises(ValueError, match="tz-naive"):
        bl.issuance_cutoff(pd.Timestamp("2024-01-08", tz="Asia/Karachi"))


def test_available_excludes_target_and_later_and_ineligible():
    w = _weekly("2024-01-01", 6, eligible=[True, False, True, True, True, True])
    avail = bl.available_before_cutoff(w, pd.Timestamp("2024-01-29"))
    assert avail["week_start"].tolist() == list(pd.to_datetime(["2024-01-01", "2024-01-15", "2024-01-22"]))


def test_weekly_frame_validation():
    w = _weekly("2024-01-01", 3)
    with pytest.raises(ValueError, match="duplicate"):
        bl.persistence(pd.concat([w, w.iloc[[0]]]), "2024-02-05")
    bad = w.copy()
    bad.loc[0, "week_start"] = pd.Timestamp("2024-01-02")
    with pytest.raises(ValueError, match="Mondays"):
        bl.persistence(bad, "2024-02-05")
    with pytest.raises(ValueError, match="missing column"):
        bl.persistence(w.drop(columns="eligible"), "2024-02-05")


# --- persistence ------------------------------------------------------------------------


def test_persistence_uses_previous_week():
    w = _weekly("2024-01-01", 5, means=[10, 20, 30, 40, 50])
    r = bl.persistence(w, "2024-01-22")  # target is the 4th week
    assert r["prediction"] == 30
    assert r["source_week_start"] == pd.Timestamp("2024-01-15")
    assert r["age_weeks"] == 1 and r["reason"] == "ok"


def test_persistence_skips_ineligible_weeks():
    w = _weekly("2024-01-01", 5, means=[10, 20, 30, 40, 50], eligible=[True, True, False, False, True])
    r = bl.persistence(w, "2024-01-29")
    assert r["prediction"] == 20
    assert r["source_week_start"] == pd.Timestamp("2024-01-08")
    assert r["age_weeks"] == 3


def test_persistence_nan_when_no_eligible_prior_week():
    w = _weekly("2024-01-01", 4, eligible=[False, False, True, True])
    r = bl.persistence(w, "2024-01-15")
    assert np.isnan(r["prediction"]) and r["reason"] == "no_eligible_prior_week"
    assert pd.isna(r["source_week_start"])
    r = bl.persistence(w, "2024-01-01")  # nothing before the record
    assert np.isnan(r["prediction"])


def test_persistence_max_age_limit():
    w = _weekly("2024-01-01", 5, eligible=[True, False, False, False, False])
    assert bl.persistence(w, "2024-02-05", max_age_weeks=5)["reason"] == "ok"
    r = bl.persistence(w, "2024-02-05", max_age_weeks=4)
    assert np.isnan(r["prediction"]) and r["reason"] == "source_too_old" and r["age_weeks"] == 5
    with pytest.raises(ValueError):
        bl.persistence(w, "2024-02-05", max_age_weeks=0)


def test_persistence_ignores_target_and_future_weeks():
    w = _weekly("2024-01-01", 8, means=np.arange(8) * 10.0)
    base = bl.persistence(w, "2024-01-22")
    w2 = _set(w, "2024-01-22", weekly_mean_observed_days=999.0)  # target week
    w2 = _set(w2, "2024-02-12", weekly_mean_observed_days=-1.0)  # later week
    future = _weekly("2024-03-04", 3, means=[5000, 5000, 5000])
    w2 = pd.concat([w2, future], ignore_index=True)
    assert bl.persistence(w2, "2024-01-22") == base


# --- seasonal climatology ---------------------------------------------------------------


@pytest.fixture
def long_weekly():
    # 2018-01-01 is a Monday; ~7 years of weeks, mean = 1000*year_index + week_index so
    # each source week is identifiable from its value.
    w = _weekly("2018-01-01", 7 * 53)
    w["weekly_mean_observed_days"] = np.arange(len(w), dtype=float)
    return w


def _expected_sources(weekly, target, window_weeks):
    t = pd.Timestamp(target)
    keep = []
    for ws in weekly["week_start"]:
        for k in range(1, 20):
            if abs(ws - (t - pd.DateOffset(years=k))) <= pd.Timedelta(days=7 * window_weeks + 3):
                keep.append(ws)
    return sorted(keep)


def test_climatology_median_of_prior_year_windows(long_weekly):
    target = "2023-07-03"
    r = bl.seasonal_climatology(long_weekly, target, **CLIM)
    expected = _expected_sources(long_weekly, target, 2)
    assert r["reason"] == "ok"
    assert r["source_week_starts"] == expected
    assert r["n_years"] == 5 and r["n_samples"] == 25  # 2018..2022, 5 weeks each
    vals = long_weekly.set_index("week_start").loc[expected, "weekly_mean_observed_days"]
    assert r["prediction"] == pytest.approx(vals.median())


def test_climatology_excludes_target_and_current_year_and_later(long_weekly):
    target = "2023-07-03"
    base = bl.seasonal_climatology(long_weekly, target, **CLIM)
    w = long_weekly.copy()
    t = pd.Timestamp(target)
    # Change everything on/after the cutoff (including the target week) and every week of
    # the current year before the cutoff (k = 0 is never part of the climatology).
    change = (w["week_start"] >= t) | (w["week_start"] >= pd.Timestamp("2023-01-01"))
    w.loc[change, "weekly_mean_observed_days"] = 1e6
    r = bl.seasonal_climatology(w, target, **CLIM)
    assert r["prediction"] == base["prediction"]
    assert r["source_week_starts"] == base["source_week_starts"]
    assert all(s + pd.Timedelta(days=6) < t for s in r["source_week_starts"])
    assert t not in r["source_week_starts"]


def test_climatology_adding_future_years_does_not_change_prediction(long_weekly):
    target = "2021-11-01"
    trimmed = long_weekly.loc[long_weekly["week_end"] < pd.Timestamp(target)]
    a = bl.seasonal_climatology(trimmed, target, **CLIM)
    b = bl.seasonal_climatology(long_weekly, target, **CLIM)
    assert a == b and a["reason"] == "ok"


def test_climatology_year_wrap(long_weekly):
    target = "2024-01-01"  # ISO week 1; window should reach back into late December
    r = bl.seasonal_climatology(long_weekly, target, window_weeks=2, min_years=1, min_samples=1)
    srcs = pd.DatetimeIndex(r["source_week_starts"])
    # k=1 anniversary is 2023-01-01 (a Sunday): nearest Monday 2023-01-02, ±2 weeks.
    k1 = pd.to_datetime(["2022-12-19", "2022-12-26", "2023-01-02", "2023-01-09", "2023-01-16"])
    assert set(k1) <= set(srcs)
    assert (srcs.month == 12).any() and (srcs.month == 1).any()
    assert r["source_week_starts"] == _expected_sources(long_weekly, target, 2)
    # Exactly 2*window+1 = 5 Mondays per prior-year window (2019..2023 anniversaries).
    for k in range(1, 6):
        a = pd.Timestamp(target) - pd.DateOffset(years=k)
        near = srcs[abs(srcs - a) <= pd.Timedelta(days=17)]
        assert len(near) == 5, (k, near)
    # k=6 (anniversary 2018-01-01) is cut by the record start: only 3 weeks exist.
    assert r["n_samples"] == 5 * 5 + 3 and r["n_years"] == 6


def test_climatology_skips_ineligible_weeks(long_weekly):
    target = "2023-07-03"
    base = bl.seasonal_climatology(long_weekly, target, **CLIM)
    drop = base["source_week_starts"][0]
    w = _set(long_weekly, drop, eligible=False)
    r = bl.seasonal_climatology(w, target, **CLIM)
    assert drop not in r["source_week_starts"] and r["n_samples"] == base["n_samples"] - 1


def test_climatology_insufficient_history_returns_nan(long_weekly):
    r = bl.seasonal_climatology(long_weekly, "2019-07-01", window_weeks=2, min_years=2, min_samples=1)
    assert np.isnan(r["prediction"]) and r["reason"] == "too_few_years" and r["n_years"] == 1
    r = bl.seasonal_climatology(long_weekly, "2019-07-01", window_weeks=2, min_years=1, min_samples=6)
    assert np.isnan(r["prediction"]) and r["reason"] == "too_few_samples"
    r = bl.seasonal_climatology(long_weekly, "2018-07-02", window_weeks=2, min_years=1, min_samples=1)
    assert np.isnan(r["prediction"]) and r["n_samples"] == 0


@pytest.mark.parametrize("kwargs", [
    dict(window_weeks=-1, min_years=1, min_samples=1),
    dict(window_weeks=26, min_years=1, min_samples=1),
    dict(window_weeks=2, min_years=0, min_samples=1),
    dict(window_weeks=2, min_years=1, min_samples=0),
    dict(window_weeks=2.0, min_years=1, min_samples=1),
])
def test_climatology_parameter_validation(long_weekly, kwargs):
    with pytest.raises(ValueError):
        bl.seasonal_climatology(long_weekly, "2023-07-03", **kwargs)


def test_climatology_parameters_required(long_weekly):
    with pytest.raises(TypeError):
        bl.seasonal_climatology(long_weekly, "2023-07-03", window_weeks=2)


# --- chronological helper ---------------------------------------------------------------


def test_predict_baselines_matches_per_call_and_is_chronological(long_weekly):
    targets = ["2023-07-10", "2022-01-03", "2023-07-03"]
    out = bl.predict_baselines(long_weekly, targets, climatology_kwargs=CLIM)
    assert out["target_week_start"].is_monotonic_increasing and len(out) == 3
    for _, row in out.iterrows():
        t = row["target_week_start"]
        assert row["persistence"] == bl.persistence(long_weekly, t)["prediction"]
        assert row["climatology"] == bl.seasonal_climatology(long_weekly, t, **CLIM)["prediction"]
        obs = long_weekly.set_index("week_start").loc[t, "weekly_mean_observed_days"]
        assert row["observed"] == obs


def test_predict_baselines_unaffected_by_future_data(long_weekly):
    targets = ["2022-01-03", "2022-06-06"]
    cut = pd.Timestamp("2022-06-06")
    past = long_weekly.loc[long_weekly["week_start"] <= cut]
    a = bl.predict_baselines(past, targets, climatology_kwargs=CLIM)
    w = long_weekly.copy()
    w.loc[w["week_start"] > cut, "weekly_mean_observed_days"] = 1e6
    b = bl.predict_baselines(w, targets, climatology_kwargs=CLIM)
    pred_cols = [c for c in a.columns if c not in ("observed", "observed_eligible")]
    pd.testing.assert_frame_equal(a[pred_cols], b[pred_cols])


def test_end_to_end_with_weekly_targets_output():
    dates = pd.date_range("2024-01-01", periods=21, freq="D")
    hours = [24] * 7 + [24] * 4 + [0] * 3 + [24] * 7  # week 2 has only 4 eligible days
    daily = pd.DataFrame({"date": dates, "hours_valid": hours, "pm25_daily_mean": [10.0] * 7 + [20.0] * 7 + [30.0] * 7})
    weekly = wt.build_weekly_targets(daily, min_valid_days=5)
    r = bl.persistence(weekly, "2024-01-22")
    assert r["prediction"] == 30.0 and r["age_weeks"] == 1
    r = bl.persistence(weekly, "2024-01-15")  # week 2 ineligible -> falls back to week 1
    assert r["prediction"] == 10.0 and r["age_weeks"] == 2
