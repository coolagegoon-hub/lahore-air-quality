"""Unit tests for src.mass_balance_features using synthetic hourly data only."""

import numpy as np
import pandas as pd
import pytest

from src import mass_balance_features as mb


def _hourly(start_pkt="2021-01-04", days=21, blh=200.0, ws=2.0):
    t = pd.date_range(start_pkt, periods=24 * days, freq="h", tz="Asia/Karachi")
    n = len(t)
    return pd.DataFrame({
        "time_pkt": t,
        "day_instant": t.tz_localize(None).normalize(),
        "blh_m": np.full(n, blh, dtype=float),
        "ws10": np.full(n, ws, dtype=float),
    })


def test_hourly_box_quantities_and_floors():
    h = _hourly(days=1, blh=500.0, ws=2.0)
    b = mb.hourly_box(h)
    assert b["vc"].iloc[0] == pytest.approx(1000.0)
    assert b["css_index"].iloc[0] == pytest.approx(1.0)                 # 1000 / VC
    assert b["flush_hours"].iloc[0] == pytest.approx(30000 / 2 / 3600)  # L / u
    assert not b["low_vent"].iloc[0]                                    # VC == LOW_VC is not < LOW_VC
    calm = mb.hourly_box(_hourly(days=1, blh=0.0, ws=0.0))
    assert np.isfinite(calm["css_index"]).all() and calm["css_index"].iloc[0] == pytest.approx(100.0)
    assert np.isfinite(calm["flush_hours"]).all()
    assert calm["night"].sum() == 12


def test_previous_week_only_and_no_leak():
    h = _hourly()                                       # PKT 2021-01-04 .. 2021-01-24
    target = pd.Timestamp("2021-01-18")                 # T−1 = 11..17 Jan
    f1 = mb.previous_week_features(mb.hourly_box(h), [target]).iloc[0]
    assert f1["mb_hours"] == 168
    assert f1["mb_prev_vc_mean"] == pytest.approx(400.0)
    assert f1["mb_prev_low_vent_hours"] == 168
    h2 = h.copy()
    h2.loc[h2["day_instant"] >= target, ["blh_m", "ws10"]] = [5000.0, 20.0]   # change week T only
    f2 = mb.previous_week_features(mb.hourly_box(h2), [target]).iloc[0]
    for c in [c for c in f1.index if c.startswith("mb_prev_")]:
        assert f2[c] == pytest.approx(f1[c])


def test_night_mean_uses_night_hours_only():
    h = _hourly()
    day_hours = ~h["time_pkt"].dt.hour.isin(mb.NIGHT_HOURS)
    h.loc[day_hours, "blh_m"] = 2000.0                  # deep daytime mixing, shallow nights
    f = mb.previous_week_features(mb.hourly_box(h), [pd.Timestamp("2021-01-18")]).iloc[0]
    assert f["mb_prev_vc_night_mean"] == pytest.approx(400.0)
    assert f["mb_prev_vc_mean"] == pytest.approx((400.0 + 4000.0) / 2)


def test_incomplete_week_is_nan_and_bad_target_raises():
    b = mb.hourly_box(_hourly())
    f = mb.previous_week_features(b, [pd.Timestamp("2021-01-04")]).iloc[0]    # T−1 before data
    assert f["mb_hours"] == 0 and np.isnan(f["mb_prev_vc_mean"])
    with pytest.raises(ValueError):
        mb.previous_week_features(b, [pd.Timestamp("2021-01-20")])
