"""Synthetic-data tests for src.stage9b_multiheight (nearest-centre assignment, input checks, verdict rule)."""

import numpy as np
import pandas as pd
import pytest

from src import stage9b_multiheight as s9b
from src import trajectory_features as tf


def test_nearest_centre_assigns_closest_shape():
    cols = tf.shape_columns()
    centres = pd.DataFrame([np.zeros(24), np.full(24, 100.0), np.full(24, -300.0)], index=[1, 2, 3], columns=cols)
    traj = pd.DataFrame([np.full(24, 10.0), np.full(24, 80.0), np.full(24, -200.0)], columns=cols)
    assert list(s9b.nearest_centre(traj, centres)) == [1, 2, 3]


def synthetic_ends(days, heights=(100.0, 250.0), hour=6, drop=None):
    rows = []
    for h in heights:
        for d in days:
            arr = pd.Timestamp(d).tz_localize("UTC") + pd.Timedelta(hours=hour)
            n = 73 if (drop is None or (h, d) != drop) else 50
            for k in range(n):
                rows.append({"arrival_utc": arr, "arrival_height_m_agl": h, "hour_back": k})
    return pd.DataFrame(rows)


def test_check_inputs_passes_and_fails():
    days = pd.date_range("2020-01-01", periods=200, freq="D")
    out = s9b.check_inputs(synthetic_ends(days), days)
    assert out["100m"]["full_73_points"] == 200 and out["250m"]["arrival_hours_utc"] == [6]
    # one short trajectory out of 200 days (0.5%) is tolerated
    out = s9b.check_inputs(synthetic_ends(days, drop=(100.0, days[5])), days)
    assert out["100m"]["days_missing_vs_500m"] == 1
    # wrong arrival hour fails
    with pytest.raises(SystemExit):
        s9b.check_inputs(synthetic_ends(days, hour=0), days)


def test_decoupling_rule():
    assert s9b.decoupling_verdict(1.2, 1.05, 1.4) == "supported"
    assert s9b.decoupling_verdict(1.1, 0.9, 1.3) == "partly supported"
    assert s9b.decoupling_verdict(0.9, 0.7, 1.1) == "not supported"
