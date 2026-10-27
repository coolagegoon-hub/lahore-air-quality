"""Synthetic-data tests for src.stage9c_gdas_comparison (separations, pair ratio, decision rule)."""

import numpy as np
import pandas as pd

from src import stage9c_gdas_comparison as s9c


def ends(lats, lons):
    arr = pd.Timestamp("2024-11-01 06:00", tz="UTC")
    return pd.DataFrame({"arrival_utc": arr, "hour_back": [24, 48, 72], "lat": lats, "lon": lons})


def test_separation_zero_for_identical_and_one_degree_latitude():
    n = ends([32.0, 33.0, 34.0], [74.0, 73.0, 72.0])
    assert np.allclose(s9c.separations(n, n)["sep_km"], 0.0)
    g = n.assign(lat=n["lat"] + 1.0)
    sep = s9c.separations(g, n)["sep_km"]
    assert np.allclose(sep, 111.19, atol=0.1)


def test_pair_ratio_recovers_known_geometric_mean_ratio():
    dates = pd.date_range("2024-12-01", periods=80, freq="D")
    cl = np.where(np.arange(80) % 2 == 0, 1, 2)
    pm = np.where(cl == 2, 200.0, 100.0)
    d = pd.DataFrame({"date": dates, "cluster": cl, "log_pm": np.log(pm), "season_year": 2025})
    r, lo, hi = s9c.pair_ratio(d)
    assert abs(r - 2.0) < 1e-9 and abs(lo - 2.0) < 1e-9 and abs(hi - 2.0) < 1e-9


def test_rule_c_flags_outside_ci_and_sign_flip():
    ncep = pd.DataFrame({"estimate": ["a", "b", "c"], "null": [1.0, 1.0, 0.0], "value": [1.2, 1.1, 0.10],
                         "ci_low": [1.0, 0.9, 0.0], "ci_high": [1.4, 1.5, 0.30], "n_days": 50})
    gdas = ncep.assign(value=[1.3, 0.95, 0.35])
    t = s9c.rule_c(ncep, gdas)
    assert list(t["gdas_outside_ncep_ci"]) == [False, False, True]
    assert list(t["opposite_sides_of_null"]) == [False, True, False]
    assert list(t["triggers"]) == [False, True, True]


def test_decision_thresholds():
    calm = pd.DataFrame({"triggers": [False] * 5})
    assert not s9c.decision(85.0, 0.9, calm)["changes_substantially"]
    assert s9c.decision(79.9, 0.9, calm)["a_cluster_agreement_below_80pct"]
    assert s9c.decision(85.0, 0.79, calm)["b_spearman_below_0.8"]
    assert s9c.decision(85.0, 0.9, pd.DataFrame({"triggers": [False, True]}))["changes_substantially"]
