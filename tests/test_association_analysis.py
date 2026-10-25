"""Unit tests for src.association_analysis using synthetic inputs only."""

import numpy as np
import pandas as pd

from src import association_analysis as aa


def test_choose_k_picks_largest_k_before_a_30pct_jump():
    tsv = pd.Series({1: 1000.0, 2: 600.0, 3: 300.0, 4: 260.0, 5: 240.0})
    k, delta = aa.choose_k(tsv)
    # Delta(3) = (600-300)/300 = 100% ; Delta(4) = 15% ; Delta(5) ~ 8%  -> k = 3
    assert k == 3
    assert round(delta[2], 1) == 66.7


def test_choose_k_falls_back_to_largest_delta():
    tsv = pd.Series({1: 100.0, 2: 90.0, 3: 85.0, 4: 80.0})
    k, _ = aa.choose_k(tsv)
    assert k == 2


def test_season_year_puts_december_in_next_winter():
    d = pd.DatetimeIndex(["2020-12-15", "2021-01-10", "2021-03-01"])
    assert list(aa.season_year(d)) == [2021, 2021, 2021]
    assert list(aa.season_of(d)) == ["winter", "winter", "pre-monsoon"]


def test_block_bootstrap_stays_within_groups_and_keeps_size():
    rng = np.random.default_rng(0)
    groups = np.array([1] * 20 + [2] * 9)
    idx = aa.block_bootstrap_indices(groups, rng, block=7)
    assert len(idx) == len(groups)
    assert set(groups[idx[:20]]) == {1} and set(groups[idx[20:]]) == {2}


def test_block_permute_keeps_values_and_groups():
    rng = np.random.default_rng(1)
    vals = np.arange(30)
    groups = np.array([0] * 15 + [1] * 15)
    out = aa.block_permute(vals, groups, rng, block=7)
    assert sorted(out[:15]) == list(range(15)) and sorted(out[15:]) == list(range(15, 30))


def test_between_variance_zero_when_groups_equal():
    y = np.array([1.0, 1.0, 2.0, 2.0])
    assert aa.between_variance(np.array([1.0, 1.0, 1.0, 1.0]), np.array([1, 1, 2, 2])) == 0.0
    assert aa.between_variance(y, np.array([1, 1, 2, 2])) == 0.25


def test_fire_exposure_counts_unique_detections_with_date_and_height_rules():
    day = pd.Timestamp("2022-11-05")
    ep = pd.DataFrame({"arrival_date": day, "point_date": [day, day, day - pd.Timedelta(days=1), day],
                       "lat": [31.0, 31.01, 31.0, 31.0], "lon": [74.0, 74.0, 74.0, 74.0],
                       "height_m_agl": [500.0, 600.0, 800.0, 2500.0]})
    fires = pd.DataFrame({
        "date_pkt": [day, day - pd.Timedelta(days=1), day - pd.Timedelta(days=3), day],
        "latitude": [31.1, 31.0, 31.0, 33.0], "longitude": [74.0, 74.0, 74.0, 74.0], "frp": [10.0, 5.0, 100.0, 7.0]})
    fe = aa.fire_exposure(ep, fires, buffers=(50.0, 25.0))
    # 10 (same day, ~11 km, near two endpoints but counted once) + 5 (previous day);
    # 100 is 3 days earlier (outside the date window); 7 is ~220 km away.
    assert fe.loc[0, "fe_50km"] == 15.0
    assert fe.loc[0, "fe_25km"] == 15.0


def test_fire_exposure_year_shift_moves_detection_dates():
    day = pd.Timestamp("2022-11-05")
    ep = pd.DataFrame({"arrival_date": [day], "point_date": [day], "lat": [31.0], "lon": [74.0], "height_m_agl": [500.0]})
    fires = pd.DataFrame({"date_pkt": [pd.Timestamp("2021-11-05")], "latitude": [31.0], "longitude": [74.0], "frp": [9.0]})
    assert aa.fire_exposure(ep, fires).loc[0, "fe_50km"] == 0.0
    assert aa.fire_exposure(ep, fires, date_shift_years=1).loc[0, "fe_50km"] == 9.0


def test_cwt_weights_by_endpoint_count():
    day = pd.Timestamp("2022-11-05")
    ep = pd.DataFrame({"arrival_date": [day] * 15, "point_date": [day] * 15,
                       "lat": [31.5] * 15, "lon": [74.5] * 15, "height_m_agl": [500.0] * 15})
    g = aa.cwt_grid(ep, pd.Series({day: 200.0}))
    assert g.loc[0, "n"] == 15 and g.loc[0, "w"] == 0.42 and g.loc[0, "wcwt"] == 84.0
