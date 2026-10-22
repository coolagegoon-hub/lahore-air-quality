"""HYSPLIT back-trajectories → per-trajectory descriptors → in-fold clustering → weekly features.

Design pre-declared in results/tables/stage4_predeclaration.md (2026-10-23).
Input: data/raw/hysplit/lahore_backtraj_endpoints.csv (2,161 daily 72 h back-trajectories,
arrival 06 UTC = 11:00 PKT, 500 m AGL, HYSPLIT v5.4.2, NCEP/NCAR Reanalysis 2.5°).

Leakage controls:
- A trajectory belongs to the PKT date of its arrival. Features for target week T use only the
  trajectories of the 7 PKT days of week T−1 (all arrive before T's Monday 00:00 PKT cutoff).
- k-means is fitted per fold only on trajectories arriving before T − 7 days (the ones that can
  feed training-row features); week T−1 trajectories are only assigned to the fitted centres.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from src import firms_features as ff

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = PROJECT_ROOT / "data" / "raw" / "hysplit" / "lahore_backtraj_endpoints.csv"
TZ = "Asia/Karachi"
SHAPE_HOURS = tuple(range(6, 73, 6))          # 6, 12, ..., 72
N_CLUSTERS = 6
N_INIT = 20
SEED = 20261021
MIN_FIT_TRAJ = 365
MIN_TRAJ_PER_WEEK = 6
SECTOR_EAST_SE = (45.0, 180.0)
SECTOR_MAX_KM = 500.0
CONT_FEATURES = ["traj_mean_dist72_km", "traj_frac_pts_east_se", "traj_mean_height_m"]


def load_endpoints(path: Path = ENDPOINTS) -> pd.DataFrame:
    d = pd.read_csv(path)
    d["arrival_utc"] = pd.to_datetime(d["arrival_time_utc"], utc=True)
    if d.duplicated(["arrival_utc", "hour_back"]).any():
        raise ValueError("duplicate (arrival, hour_back) rows")
    return d


def per_trajectory(d: pd.DataFrame) -> pd.DataFrame:
    """One row per trajectory: PKT arrival date, continuous descriptors and the km shape vector."""
    lat0, lon0 = ff.LAHORE
    out = pd.DataFrame(index=pd.DatetimeIndex(sorted(d["arrival_utc"].unique()), name="arrival_utc"))
    out["date_pkt"] = out.index.tz_convert(TZ).tz_localize(None).normalize()
    counts = d.groupby("arrival_utc").size()
    out["n_points"] = counts.reindex(out.index).to_numpy()

    back = d[d["hour_back"] >= 1].copy()
    dist, bear = ff.distance_bearing(back["lat"], back["lon"])
    back["in_east_se"] = (dist < SECTOR_MAX_KM) & (bear >= SECTOR_EAST_SE[0]) & (bear < SECTOR_EAST_SE[1])
    g = back.groupby("arrival_utc")
    out["traj_frac_pts_east_se"] = g["in_east_se"].mean().reindex(out.index).to_numpy()
    out["traj_mean_height_m"] = g["height_m_agl"].mean().reindex(out.index).to_numpy()
    end = d[d["hour_back"] == 72].set_index("arrival_utc")
    d72, _ = ff.distance_bearing(end["lat"], end["lon"])
    out["traj_mean_dist72_km"] = pd.Series(d72, index=end.index).reindex(out.index).to_numpy()

    # shape vector: km east (x) / north (y) of the receptor at hours 6..72 (equirectangular)
    shp = d[d["hour_back"].isin(SHAPE_HOURS)]
    x = ff.EARTH_R_KM * np.cos(np.radians(lat0)) * np.radians(shp["lon"] - lon0)
    y = ff.EARTH_R_KM * np.radians(shp["lat"] - lat0)
    wide_x = pd.Series(x.to_numpy(), index=pd.MultiIndex.from_arrays([shp["arrival_utc"], shp["hour_back"]])).unstack()
    wide_y = pd.Series(y.to_numpy(), index=pd.MultiIndex.from_arrays([shp["arrival_utc"], shp["hour_back"]])).unstack()
    for h in SHAPE_HOURS:
        out[f"x{h}"] = wide_x[h].reindex(out.index).to_numpy()
        out[f"y{h}"] = wide_y[h].reindex(out.index).to_numpy()
    return out


def shape_columns() -> list[str]:
    return [f"{a}{h}" for h in SHAPE_HOURS for a in ("x", "y")]


def week_start(dates: pd.Series | pd.DatetimeIndex) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(dates)
    return dates - pd.to_timedelta(dates.dayofweek, unit="D")


def weekly_continuous(traj: pd.DataFrame) -> pd.DataFrame:
    """Continuous features per TARGET week T (from trajectories of week T−1). No fitting involved."""
    t = traj.copy()
    t["target_week_start"] = week_start(t["date_pkt"]) + pd.Timedelta(days=7)
    g = t.groupby("target_week_start")
    w = g[CONT_FEATURES].mean()
    w["traj_n"] = g.size()
    w.loc[w["traj_n"] < MIN_TRAJ_PER_WEEK, CONT_FEATURES] = np.nan
    return w


def fit_fold_clusters(traj: pd.DataFrame, cutoff: pd.Timestamp, k: int = N_CLUSTERS, seed: int = SEED):
    """Fit k-means on trajectories arriving before cutoff − 7 days only. Returns None if too few."""
    fit_rows = traj[traj["date_pkt"] < cutoff - pd.Timedelta(days=7)]
    if len(fit_rows) < MIN_FIT_TRAJ:
        return None
    km = KMeans(n_clusters=k, n_init=N_INIT, random_state=seed)
    km.fit(fit_rows[shape_columns()].to_numpy(float))
    return km


def fold_cluster_fractions(traj: pd.DataFrame, km: KMeans, cutoff: pd.Timestamp, k: int = N_CLUSTERS) -> pd.DataFrame:
    """Weekly cluster shares per TARGET week (<= cutoff) using this fold's centres; trajectories
    arriving on/after the cutoff are never used. NaN if fewer than MIN_TRAJ_PER_WEEK trajectories."""
    use = traj[traj["date_pkt"] < cutoff]
    labels = km.predict(use[shape_columns()].to_numpy(float))
    onehot = pd.DataFrame(np.eye(k)[labels], index=use.index, columns=[f"traj_frac_c{i + 1}" for i in range(k)])
    onehot["target_week_start"] = week_start(use["date_pkt"]) + pd.Timedelta(days=7)
    g = onehot.groupby("target_week_start")
    fr = g.mean()
    n = g.size()
    fr.loc[n < MIN_TRAJ_PER_WEEK, :] = np.nan
    return fr
