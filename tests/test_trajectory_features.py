"""Unit tests for src.trajectory_features and src.stage4_trajectory_model (synthetic data only)."""

import numpy as np
import pandas as pd
import pytest

from src import firms_features as ff
from src import stage4_trajectory_model as s4
from src import trajectory_features as tf


def _endpoints(start="2021-01-04", days=60, direction=None, seed=0):
    """Synthetic straight-line back-trajectories; direction per day in degrees (bearing of origin)."""
    rng = np.random.default_rng(seed)
    lat0, lon0 = ff.LAHORE
    rows = []
    for i, day in enumerate(pd.date_range(start, periods=days, freq="D")):
        arr = day + pd.Timedelta(hours=6)  # 06 UTC
        b = direction[i] if direction is not None else rng.choice([90.0, 270.0])
        for h in range(73):
            dist_km = 10.0 * h
            dlat = dist_km * np.cos(np.radians(b)) / 111.2
            dlon = dist_km * np.sin(np.radians(b)) / (111.2 * np.cos(np.radians(lat0)))
            rows.append({"arrival_time_utc": arr.strftime("%Y-%m-%dT%H:%M:%SZ"), "arrival_height_m_agl": 500.0,
                         "hour_back": h, "point_time_utc": (arr - pd.Timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "lat": lat0 + dlat, "lon": lon0 + dlon, "height_m_agl": 500.0 + h, "pressure_hpa": 900.0})
    df = pd.DataFrame(rows)
    df["arrival_utc"] = pd.to_datetime(df["arrival_time_utc"], utc=True)
    return df


def test_per_trajectory_descriptors_and_pkt_date():
    t = tf.per_trajectory(_endpoints(days=2, direction=[90.0, 270.0]))
    assert len(t) == 2 and (t["n_points"] == 73).all()
    # 06 UTC arrival = 11:00 PKT on the same calendar date
    assert t["date_pkt"].iloc[0] == pd.Timestamp("2021-01-04")
    assert t["traj_mean_dist72_km"].iloc[0] == pytest.approx(720, rel=0.02)
    assert t["traj_frac_pts_east_se"].iloc[0] > 0.6      # due east: points within 500 km are in sector
    assert t["traj_frac_pts_east_se"].iloc[1] == 0.0     # due west: never in the east/south-east sector
    assert t["x72"].iloc[0] > 600 and abs(t["y72"].iloc[0]) < 5


def test_weekly_continuous_maps_week_to_next_target_and_requires_six():
    t = tf.per_trajectory(_endpoints(start="2021-01-04", days=10))   # Mon 4 Jan .. Wed 13 Jan
    w = tf.weekly_continuous(t)
    assert pd.Timestamp("2021-01-11") in w.index                    # week 4–10 Jan feeds target 11 Jan
    assert w.loc[pd.Timestamp("2021-01-11"), "traj_n"] == 7
    assert w.loc[pd.Timestamp("2021-01-18"), "traj_n"] == 3          # partial week
    assert np.isnan(w.loc[pd.Timestamp("2021-01-18"), "traj_mean_dist72_km"])


def test_fold_clustering_uses_only_trajectories_before_cutoff_minus_7_days():
    traj = tf.per_trajectory(_endpoints(start="2020-01-06", days=420, seed=1))
    cutoff = pd.Timestamp("2021-02-01")
    km1 = tf.fit_fold_clusters(traj, cutoff, k=2)
    traj2 = traj.copy()
    late = traj2["date_pkt"] >= cutoff - pd.Timedelta(days=7)
    traj2.loc[late, tf.shape_columns()] = 99999.0                     # change week T−1 and later
    km2 = tf.fit_fold_clusters(traj2, cutoff, k=2)
    assert np.allclose(np.sort(km1.cluster_centers_, axis=0), np.sort(km2.cluster_centers_, axis=0))
    # too few trajectories -> no clustering
    assert tf.fit_fold_clusters(traj, pd.Timestamp("2020-06-01"), k=2) is None


def test_fold_fractions_ignore_trajectories_on_or_after_cutoff():
    traj = tf.per_trajectory(_endpoints(start="2020-01-06", days=420, seed=2))
    cutoff = pd.Timestamp("2021-02-01")
    km = tf.fit_fold_clusters(traj, cutoff, k=2)
    fr = tf.fold_cluster_fractions(traj, km, cutoff, k=2)
    assert fr.index.max() <= cutoff
    row = fr.loc[cutoff]                                              # features of target T = week T−1
    assert row.sum() == pytest.approx(1.0)


def _table_and_traj(n_weeks=110, seed=3):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2020-01-06")
    days = n_weeks * 7
    dirs = np.repeat(rng.choice([90.0, 270.0], size=n_weeks), 7)
    traj = tf.per_trajectory(_endpoints(start=str(start.date()), days=days, direction=dirs, seed=seed))
    ws = pd.date_range(start + pd.Timedelta(days=7), periods=n_weeks - 1, freq="7D")
    east_prev = (dirs[::7][:-1] == 90.0).astype(float)                  # previous week's direction
    y = 100 + 80 * east_prev + rng.normal(scale=1, size=len(ws))
    table = pd.DataFrame({"target_week_start": ws, "week_end": ws + pd.Timedelta(days=6),
                          "weekly_mean_observed_days": y, "eligible": True, "partial_week": False,
                          "noise": rng.normal(size=len(ws))})
    return table, traj


def test_walk_forward_traj_is_leak_free_and_learns_direction():
    fast = {"n_estimators": 30, "min_samples_leaf": 2, "max_features": 1.0, "random_state": 0, "n_jobs": 1}
    table, traj = _table_and_traj()
    tgt = table["target_week_start"].iloc[[100]]
    p1 = s4.walk_forward_traj(table, ["noise"], tgt, traj, k=2, params=fast, min_train=52)
    assert p1.loc[0, "reason"] == "ok"
    expected = table.loc[100, "weekly_mean_observed_days"]
    assert abs(p1.loc[0, "pred"] - expected) < 20                      # direction signal is learned
    # changing the target week and everything after must not change the prediction
    t_cut = table.loc[100, "target_week_start"]
    table2 = table.copy()
    table2.loc[100:, "weekly_mean_observed_days"] = 1e6
    traj2 = traj.copy()
    traj2.loc[traj2["date_pkt"] >= t_cut, tf.shape_columns() + tf.CONT_FEATURES] = 12345.0
    p2 = s4.walk_forward_traj(table2, ["noise"], tgt, traj2, k=2, params=fast, min_train=52)
    assert p2.loc[0, "pred"] == pytest.approx(p1.loc[0, "pred"])
