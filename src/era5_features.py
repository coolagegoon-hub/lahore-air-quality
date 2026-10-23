"""ERA5 weather → daily Lahore-time series → previous-week features for weekly PM2.5 forecasts.

Input: the yearly ERA5 point time-series zips in data/raw/era5/ (src.download_era5;
dataset reanalysis-era5-single-levels-timeseries, grid point 31.50 N 74.25 E). Times are UTC.

Conventions (fixed before any modelling results were seen):
- Time: UTC → PKT (Asia/Karachi, UTC+05:00, no DST).
- Day assignment: instantaneous variables belong to the PKT date of their valid time.
  Hourly accumulations (tp, ssrd, strd, sshf, slhf, fdir) cover the hour ENDING at valid_time
  (ERA5 convention), so they are assigned to the PKT date of (valid_time − 1 h), matching the
  hour-ending day convention of the PM2.5 series (src.pm25_qc).
- Units: K → °C; Pa → hPa; precipitation m → mm; J m⁻² per hour → W m⁻² (÷ 3600). Heat
  fluxes keep the ERA5 sign convention (positive = downward into the surface).
- Derived: wind speed at 10 m and 100 m; relative humidity from t2m and d2m (Magnus formula,
  over water); calm hour = 10 m wind speed < CALM_MS.
- Weekly features for target week T (Monday–Sunday, PKT) are computed ONLY from the seven PKT
  days of week T−1, which ends at the forecast cutoff (Monday 00:00 PKT of week T). Nothing from
  week T is used.
- Availability caveat: ERA5 is a reanalysis published days after real time, so in a real
  forecast week T−1's ERA5 would not yet exist at the cutoff. This retrospective study uses it as
  a stand-in for operational analyses that would be available; this is a documented assumption,
  not a leak of target-week weather.
- No imputation. The ERA5 record has no missing hours (checked 2026-10-20); a week with any
  missing day gets NaN features and is reported.

Usage:
    python -m src.era5_features
"""

from __future__ import annotations

import glob
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "era5"
TZ = "Asia/Karachi"
CALM_MS = 1.0
RAIN_DAY_MM = 1.0
ACCUMULATED = ("tp", "ssrd", "strd", "sshf", "slhf", "fdir")


def load_raw(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Concatenate all yearly CSVs (inside the zips) into one hourly UTC frame."""
    frames = []
    for path in sorted(glob.glob(str(raw_dir / "era5_ts_*.zip"))):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith(".csv")]
            if len(names) != 1:
                raise ValueError(f"{path}: expected one CSV, found {names}")
            frames.append(pd.read_csv(io.BytesIO(z.read(names[0]))))
    if not frames:
        raise FileNotFoundError(f"no era5_ts_*.zip files in {raw_dir}")
    df = pd.concat(frames, ignore_index=True)
    df["valid_time"] = pd.to_datetime(df["valid_time"], utc=True)
    if df["valid_time"].duplicated().any():
        raise ValueError(f"{int(df['valid_time'].duplicated().sum())} duplicate hours")
    return df.sort_values("valid_time", ignore_index=True)


def relative_humidity(t_c: pd.Series, td_c: pd.Series) -> pd.Series:
    """RH (%) from air and dewpoint temperature in °C (Magnus, over water)."""
    a, b = 17.625, 243.04
    return 100 * np.exp(a * td_c / (b + td_c) - a * t_c / (b + t_c))


def to_hourly_pkt(raw: pd.DataFrame) -> pd.DataFrame:
    """Convert units, derive variables, and attach the PKT day each record belongs to."""
    h = pd.DataFrame(index=raw.index)
    h["time_pkt"] = raw["valid_time"].dt.tz_convert(TZ)
    h["t2m_c"] = raw["t2m"] - 273.15
    h["d2m_c"] = raw["d2m"] - 273.15
    h["rh_pct"] = relative_humidity(h["t2m_c"], h["d2m_c"])
    h["u10"], h["v10"] = raw["u10"], raw["v10"]
    h["ws10"] = np.hypot(raw["u10"], raw["v10"])
    h["ws100"] = np.hypot(raw["u100"], raw["v100"])
    h["gust10"] = raw["fg10"]
    h["blh_m"] = raw["blh"]
    h["sp_hpa"] = raw["sp"] / 100
    h["msl_hpa"] = raw["msl"] / 100
    h["tcc"] = raw["tcc"]
    h["tp_mm"] = raw["tp"] * 1000
    h["ssrd_wm2"] = raw["ssrd"] / 3600
    h["sshf_wm2"] = raw["sshf"] / 3600
    h["calm"] = h["ws10"] < CALM_MS
    instant_day = h["time_pkt"].dt.tz_localize(None).dt.normalize()
    accum_day = (h["time_pkt"] - pd.Timedelta(hours=1)).dt.tz_localize(None).dt.normalize()
    h["day_instant"] = instant_day
    h["day_accum"] = accum_day
    return h


def daily(h: pd.DataFrame) -> pd.DataFrame:
    """Daily (PKT) aggregates with hour counts so incomplete days are visible."""
    gi = h.groupby("day_instant")
    ga = h.groupby("day_accum")
    d = pd.DataFrame({
        "n_hours_instant": gi.size(),
        "t2m_mean_c": gi["t2m_c"].mean(), "t2m_min_c": gi["t2m_c"].min(), "t2m_max_c": gi["t2m_c"].max(),
        "d2m_mean_c": gi["d2m_c"].mean(), "rh_mean_pct": gi["rh_pct"].mean(),
        "u10_mean": gi["u10"].mean(), "v10_mean": gi["v10"].mean(),
        "ws10_mean": gi["ws10"].mean(), "ws100_mean": gi["ws100"].mean(), "gust10_max": gi["gust10"].max(),
        "calm_hours": gi["calm"].sum(),
        "blh_mean_m": gi["blh_m"].mean(), "blh_min_m": gi["blh_m"].min(), "blh_max_m": gi["blh_m"].max(),
        "sp_mean_hpa": gi["sp_hpa"].mean(), "msl_mean_hpa": gi["msl_hpa"].mean(),
        "tcc_mean": gi["tcc"].mean(),
    })
    acc = pd.DataFrame({
        "n_hours_accum": ga.size(),
        "tp_sum_mm": ga["tp_mm"].sum(),
        "ssrd_mean_wm2": ga["ssrd_wm2"].mean(), "sshf_mean_wm2": ga["sshf_wm2"].mean(),
    })
    d = d.join(acc, how="outer")
    d.index.name = "date"
    d["complete_day"] = d["n_hours_instant"].eq(24) & d["n_hours_accum"].eq(24)
    return d


WEEKLY_SPEC = {
    # feature name: (daily column, weekly aggregation over the 7 days of week T−1)
    "t2m_mean_c": ("t2m_mean_c", "mean"), "t2m_min_c": ("t2m_min_c", "mean"), "t2m_max_c": ("t2m_max_c", "mean"),
    "rh_mean_pct": ("rh_mean_pct", "mean"), "d2m_mean_c": ("d2m_mean_c", "mean"),
    "u10_mean": ("u10_mean", "mean"), "v10_mean": ("v10_mean", "mean"),
    "ws10_mean": ("ws10_mean", "mean"), "ws100_mean": ("ws100_mean", "mean"), "gust10_max": ("gust10_max", "max"),
    "calm_hours": ("calm_hours", "sum"),
    "blh_mean_m": ("blh_mean_m", "mean"), "blh_min_m": ("blh_min_m", "mean"), "blh_max_m": ("blh_max_m", "mean"),
    "sp_mean_hpa": ("sp_mean_hpa", "mean"), "msl_mean_hpa": ("msl_mean_hpa", "mean"),
    "tcc_mean": ("tcc_mean", "mean"), "tp_sum_mm": ("tp_sum_mm", "sum"),
    "rain_days": ("tp_sum_mm", lambda s: (s >= RAIN_DAY_MM).sum()),
    "ssrd_mean_wm2": ("ssrd_mean_wm2", "mean"), "sshf_mean_wm2": ("sshf_mean_wm2", "mean"),
}


def previous_week_features(d: pd.DataFrame, target_week_starts) -> pd.DataFrame:
    """One row per target week T: features from the 7 PKT days of week T−1 only.

    If any of those 7 days is missing or incomplete, all features for T are NaN (no imputation).
    """
    rows = []
    for t in pd.DatetimeIndex(target_week_starts):
        if t.day_of_week != 0 or t != t.normalize():
            raise ValueError(f"target week must start on a Monday 00:00, got {t}")
        days = pd.date_range(t - pd.Timedelta(days=7), t - pd.Timedelta(days=1), freq="D")
        w = d.reindex(days)
        row = {"target_week_start": t, "era5_days_complete": int(w["complete_day"].eq(True).sum())}
        ok = row["era5_days_complete"] == 7
        for name, (col, how) in WEEKLY_SPEC.items():
            row[f"era5_prev_{name}"] = (w[col].agg(how) if ok else np.nan)
        rows.append(row)
    out = pd.DataFrame(rows)
    feat = [c for c in out.columns if c.startswith("era5_prev_")]
    out[feat] = out[feat].astype(float)
    return out


def main() -> None:
    raw = load_raw()
    h = to_hourly_pkt(raw)
    d = daily(h)
    weekly = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "pm25_weekly_target.csv", parse_dates=["week_start"])
    feats = previous_week_features(d, weekly["week_start"])

    d.to_csv(PROJECT_ROOT / "data" / "processed" / "era5_daily_pkt.csv")
    feats.to_csv(PROJECT_ROOT / "data" / "processed" / "era5_prev_week_features.csv", index=False)

    full_days = d[d["complete_day"]]
    summary = {
        "hours": len(h), "first_utc": str(raw["valid_time"].min()), "last_utc": str(raw["valid_time"].max()),
        "grid_point": raw[["latitude", "longitude"]].drop_duplicates().values.tolist(),
        "daily_rows": len(d), "complete_days": int(d["complete_day"].sum()),
        "incomplete_days": d.index[~d["complete_day"]].strftime("%Y-%m-%d").tolist(),
        "target_weeks": len(feats), "target_weeks_with_features": int(feats["era5_days_complete"].eq(7).sum()),
        "feature_columns": [c for c in feats.columns if c.startswith("era5_prev_")],
    }
    print(json.dumps(summary, indent=2))
    # sanity: monthly climatology of a few daily values (for plausibility checks only)
    m = full_days.groupby(full_days.index.month)[["t2m_mean_c", "t2m_max_c", "rh_mean_pct", "blh_mean_m",
                                                  "ws10_mean", "tp_sum_mm", "calm_hours"]].mean().round(1)
    m["tp_sum_mm"] = full_days.groupby(full_days.index.month)["tp_sum_mm"].sum().div(
        full_days.groupby(full_days.index.month).size()).mul(30).round(1)  # mm per 30 days
    print("\nMonthly means of daily values (tp = mm per 30 days):\n", m.to_string())


if __name__ == "__main__":
    main()
