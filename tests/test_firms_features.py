"""Unit tests for src.firms_features using synthetic detections only."""

import numpy as np
import pandas as pd
import pytest

from src import firms_features as ff


def _det(lat, lon, date="2021-01-12", time=800, conf="n", typ=0, frp=10.0):
    return {"latitude": lat, "longitude": lon, "acq_date": date, "acq_time": time,
            "confidence": conf, "type": typ, "frp": frp}


def test_distance_and_bearing():
    d, b = ff.distance_bearing([ff.LAHORE[0]], [ff.LAHORE[1] + 1.0])      # 1° due east
    assert d[0] == pytest.approx(94.8, abs=1.0) and b[0] == pytest.approx(90, abs=1)
    d, b = ff.distance_bearing([ff.LAHORE[0] - 1.0], [ff.LAHORE[1]])      # 1° due south
    assert d[0] == pytest.approx(111.2, abs=1.0) and b[0] == pytest.approx(180, abs=0.5)


def test_filters_rings_sectors_and_pkt_date():
    lat0, lon0 = ff.LAHORE
    raw = pd.DataFrame([
        _det(lat0, lon0 + 0.5),                     # ~47 km east -> r0_100, east_se
        _det(lat0 - 2.0, lon0),                     # ~222 km south -> r100_300 (180° counts as west_s)
        _det(lat0, lon0 - 4.0),                     # ~380 km west -> r300_500, west_s
        _det(lat0 + 2.0, lon0),                     # ~222 km north -> ring only, no sector
        _det(lat0, lon0 + 0.5, conf="l"),           # low confidence -> dropped
        _det(lat0, lon0 + 0.5, typ=2),              # static source -> dropped
        _det(lat0, lon0 + 0.5, date="2021-01-12", time=2000),  # 20:00 UTC = 01:00 PKT next day
    ])
    k = ff.prepare(raw)
    assert len(k) == 5
    assert k["ring"].tolist() == ["r0_100", "r100_300", "r300_500", "r100_300", "r0_100"]
    assert k["sector"].tolist() == ["east_se", "west_s", "west_s", None, "east_se"]
    assert k["date_pkt"].dt.strftime("%Y-%m-%d").tolist()[-1] == "2021-01-13"


def test_daily_zero_fill_and_previous_week_only():
    lat0, lon0 = ff.LAHORE
    raw = pd.DataFrame([
        _det(lat0, lon0 + 0.5, date="2021-01-12", frp=5.0),   # week T−1 (Mon 11 – Sun 17 Jan)
        _det(lat0, lon0 + 0.5, date="2021-01-13", frp=7.0),   # week T−1
        _det(lat0, lon0 + 0.5, date="2021-01-19", frp=99.0),  # week T (target) -> must be ignored
    ])
    d = ff.daily_counts(ff.prepare(raw), "2021-01-04", "2021-01-31")
    assert d.loc["2021-01-14", "r0_100_count"] == 0                       # no fire = 0, not NaN
    f = ff.previous_week_features(d, [pd.Timestamp("2021-01-18")]).iloc[0]
    assert f["fire_prev_r0_100_count"] == 2
    assert f["fire_prev_r0_100_frp_mw"] == pytest.approx(12.0)
    assert f["fire_prev_east_se_count"] == 2 and f["fire_prev_west_s_count"] == 0


def test_week_outside_record_is_nan_and_bad_target_raises():
    d = ff.daily_counts(ff.prepare(pd.DataFrame([_det(*ff.LAHORE)])), "2021-01-11", "2021-01-31")
    f = ff.previous_week_features(d, [pd.Timestamp("2021-01-11")]).iloc[0]   # T−1 before record
    assert np.isnan(f["fire_prev_r0_100_count"])
    with pytest.raises(ValueError):
        ff.previous_week_features(d, [pd.Timestamp("2021-01-13")])
