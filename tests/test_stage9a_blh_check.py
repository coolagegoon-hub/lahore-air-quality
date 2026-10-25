"""Synthetic-data test for src.stage9a_blh_check."""

import numpy as np
import pandas as pd

from src import stage9a_blh_check as s9


def test_shares_terciles_and_arrival_hour():
    days = pd.date_range("2020-01-01", "2020-01-30", freq="D")
    hourly = pd.DataFrame({"day": np.repeat(days, 24), "hour_pkt": np.tile(np.arange(24), len(days))})
    # BLH 200 m before noon, 800 m after; at 11:00 PKT: 50 m on the 10 dirtiest days, else 300 m
    hourly["blh_m"] = np.where(hourly["hour_pkt"] < 12, 200.0, 800.0)
    pm = pd.DataFrame({"date": days, "pm25_daily_mean": np.arange(1, 31, dtype=float)})
    dirty = days[-10:]
    hourly.loc[(hourly["hour_pkt"] == 11) & hourly["day"].isin(dirty), "blh_m"] = 50.0
    hourly.loc[(hourly["hour_pkt"] == 11) & ~hourly["day"].isin(dirty), "blh_m"] = 300.0
    out = s9.summarise(hourly, pm).set_index("group")
    w = out.loc["winter"]
    assert w["n_hours"] == 30 * 24 and w["n_days_0600utc"] == 30
    assert w["all_hours_pct_below_500m"] == 50.0                    # hours 0–11 below 500 m
    assert w["arrival_pct_below_500m"] == 100.0 and w["arrival_pct_below_250m"] == round(100 * 10 / 30, 1)
    assert w["arrival_pct_below_100m"] == round(100 * 10 / 30, 1)
    assert w["pm_high_third_pct_below_500m_0600utc"] == 100.0 and w["pm_high_third_n_days"] == 10
    assert out.loc["Oct-Jan", "n_days_0600utc"] == 30
