"""Unit tests for src.era5_features using synthetic ERA5-like data only."""

import numpy as np
import pandas as pd
import pytest

from src import era5_features as ef


def _raw(start_utc="2021-01-03 19:00", hours=24 * 21, **overrides):
    t = pd.date_range(start_utc, periods=hours, freq="h", tz="UTC")
    n = len(t)
    raw = pd.DataFrame({
        "valid_time": t, "t2m": np.full(n, 293.15), "d2m": np.full(n, 283.15),
        "u10": np.full(n, 3.0), "v10": np.full(n, 4.0), "u100": np.full(n, 6.0), "v100": np.full(n, 8.0),
        "fg10": np.full(n, 7.0), "blh": np.full(n, 500.0), "sp": np.full(n, 98000.0), "msl": np.full(n, 101000.0),
        "tcc": np.full(n, 0.5), "tp": np.zeros(n), "ssrd": np.full(n, 3600.0 * 100), "sshf": np.full(n, -3600.0 * 20),
        "latitude": 31.5, "longitude": 74.25,
    })
    for k, v in overrides.items():
        raw[k] = v
    return raw


def test_units_and_derived_variables():
    h = ef.to_hourly_pkt(_raw(hours=3))
    assert h["t2m_c"].iloc[0] == pytest.approx(20.0)
    assert h["sp_hpa"].iloc[0] == pytest.approx(980.0)
    assert h["ws10"].iloc[0] == pytest.approx(5.0) and h["ws100"].iloc[0] == pytest.approx(10.0)
    assert h["ssrd_wm2"].iloc[0] == pytest.approx(100.0) and h["sshf_wm2"].iloc[0] == pytest.approx(-20.0)
    assert ef.relative_humidity(pd.Series([15.0]), pd.Series([15.0])).iloc[0] == pytest.approx(100.0)
    assert 50 < h["rh_pct"].iloc[0] < 55  # 20 °C air, 10 °C dewpoint ≈ 52 %


def test_utc_to_pkt_day_assignment():
    # 19:00 UTC = 00:00 PKT next day (instantaneous -> that PKT day);
    # an accumulation valid at 19:00 UTC covers 23:00–00:00 PKT -> the previous PKT day
    h = ef.to_hourly_pkt(_raw("2021-01-03 19:00", hours=1))
    assert h["time_pkt"].iloc[0] == pd.Timestamp("2021-01-04 00:00", tz="Asia/Karachi")
    assert h["day_instant"].iloc[0] == pd.Timestamp("2021-01-04")
    assert h["day_accum"].iloc[0] == pd.Timestamp("2021-01-03")


def test_daily_counts_rain_and_calm():
    n = 24 * 21
    tp = np.zeros(n)
    tp[30] = 0.002  # 2 mm in one hour
    u = np.full(n, 3.0)
    u[40:43] = 0.1
    v = np.full(n, 4.0)
    v[40:43] = 0.1
    d = ef.daily(ef.to_hourly_pkt(_raw(tp=tp, u10=u, v10=v)))
    assert d["tp_sum_mm"].sum() == pytest.approx(2.0)
    assert int(d["calm_hours"].sum()) == 3
    assert d.loc[pd.Timestamp("2021-01-05"), "complete_day"]


def test_previous_week_only_and_no_leak_from_target_week():
    raw = _raw()                                     # covers PKT 2021-01-04 .. 2021-01-24
    d = ef.daily(ef.to_hourly_pkt(raw))
    target = pd.Timestamp("2021-01-18")              # week T; T−1 = 2021-01-11..17
    f1 = ef.previous_week_features(d, [target]).iloc[0]
    assert f1["era5_days_complete"] == 7
    assert f1["era5_prev_t2m_mean_c"] == pytest.approx(20.0)
    # change all weather from the cutoff onwards (week T): features must not change
    t = raw["valid_time"].dt.tz_convert("Asia/Karachi")
    raw2 = raw.copy()
    raw2.loc[t >= pd.Timestamp("2021-01-18", tz="Asia/Karachi"), "t2m"] = 400.0
    d2 = ef.daily(ef.to_hourly_pkt(raw2))
    f2 = ef.previous_week_features(d2, [target]).iloc[0]
    assert f2["era5_prev_t2m_mean_c"] == pytest.approx(f1["era5_prev_t2m_mean_c"])
    # changing week T−1 does change them
    raw3 = raw.copy()
    raw3.loc[(t >= pd.Timestamp("2021-01-11", tz="Asia/Karachi")) & (t < pd.Timestamp("2021-01-18", tz="Asia/Karachi")), "t2m"] = 303.15
    f3 = ef.previous_week_features(ef.daily(ef.to_hourly_pkt(raw3)), [target]).iloc[0]
    assert f3["era5_prev_t2m_mean_c"] == pytest.approx(30.0)


def test_incomplete_previous_week_gives_nan_and_bad_target_raises():
    d = ef.daily(ef.to_hourly_pkt(_raw()))
    f = ef.previous_week_features(d, [pd.Timestamp("2021-01-04")]).iloc[0]   # T−1 is before the data
    assert f["era5_days_complete"] == 0 and np.isnan(f["era5_prev_t2m_mean_c"])
    with pytest.raises(ValueError):
        ef.previous_week_features(d, [pd.Timestamp("2021-01-06")])           # not a Monday
