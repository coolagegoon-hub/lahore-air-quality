"""NASA FIRMS fire detections → daily Lahore-time counts → previous-week fire features.

Input: data/raw/firms/<SOURCE>/*.csv from src.download_firms (standard-processing archives,
box 69–78 E, 27–35 N, 2019-04-01 → 2025-02-28; acquisition date/time in UTC).

Design (approved by the user 2026-10-21; fixed before any modelling results were seen):
- Primary source: VIIRS_SNPP_SP (consistent over the whole period, 375 m pixels).
  VIIRS_NOAA20_SP is used only as a cross-check; the two are NOT summed because the same fire
  is often detected by both satellites.
- Detections kept: type == 0 (presumed vegetation fire) and confidence in {"n", "h"}
  (nominal, high). Dropped: low confidence, static land sources (type 2), offshore (type 3).
- Time: acq_date + acq_time (HHMM, UTC) → PKT (UTC+05:00); each detection belongs to its PKT
  calendar date.
- Location relative to the PM2.5 monitor (31.560078 N, 74.33589 E): great-circle distance (km)
  and initial bearing (degrees clockwise from north).
- Rings: 0–100, 100–300, 300–500 km. Sectors (within 0–500 km): "east_se" = bearing 45°–180°
  (Indian Punjab, Haryana), "west_s" = bearing 180°–315° (Pakistani Punjab). The northern
  sector (315°–45°) counts towards ring totals only.
  NOTE: the download box reaches only ~350–390 km to the east and north of Lahore, so the
  300–500 km ring is truncated on those sides; it is complete to the south and west.
- Features for target week T (Mon–Sun PKT) use ONLY fires detected on the 7 PKT days of week
  T−1 (before the Monday 00:00 PKT cutoff): detection count and total fire radiative power
  (FRP, MW) per ring and per sector.
- A day with no detections is a true zero (no fires detected), not missing data. FIRMS SP files
  do not flag missed satellite passes, so cloud cover or outages can hide fires; this is a
  known limitation and is not corrected.

Usage:
    python -m src.firms_features
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "firms"
TZ = "Asia/Karachi"
LAHORE = (31.560078, 74.33589)
PRIMARY = "VIIRS_SNPP_SP"
CROSSCHECK = "VIIRS_NOAA20_SP"
KEEP_CONFIDENCE = ("n", "h")
RINGS = {"r0_100": (0, 100), "r100_300": (100, 300), "r300_500": (300, 500)}
SECTORS = {"east_se": (45, 180), "west_s": (180, 315)}
MAX_KM = 500
EARTH_R_KM = 6371.0088


def load_source(source: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    files = sorted(glob.glob(str(raw_dir / source / "*.csv")))
    if not files:
        raise FileNotFoundError(f"no files for {source} in {raw_dir}")
    frames = [pd.read_csv(f) for f in files]
    return pd.concat([f for f in frames if len(f)], ignore_index=True)


def distance_bearing(lat, lon, lat0: float = LAHORE[0], lon0: float = LAHORE[1]) -> tuple[np.ndarray, np.ndarray]:
    """Great-circle distance (km) and initial bearing (0–360°, from north) from (lat0, lon0)."""
    p0, l0 = np.radians(lat0), np.radians(lon0)
    p1, l1 = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    dl = l1 - l0
    a = np.sin((p1 - p0) / 2) ** 2 + np.cos(p0) * np.cos(p1) * np.sin(dl / 2) ** 2
    dist = 2 * EARTH_R_KM * np.arcsin(np.sqrt(a))
    y = np.sin(dl) * np.cos(p1)
    x = np.cos(p0) * np.sin(p1) - np.sin(p0) * np.cos(p1) * np.cos(dl)
    bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
    return dist, bearing


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Filter detections, attach PKT date, distance, bearing, ring and sector."""
    kept = df[(df["type"] == 0) & df["confidence"].astype(str).isin(KEEP_CONFIDENCE)].copy()
    hhmm = kept["acq_time"].astype(int)
    utc = (pd.to_datetime(kept["acq_date"]) + pd.to_timedelta(hhmm // 100, unit="h")
           + pd.to_timedelta(hhmm % 100, unit="min")).dt.tz_localize("UTC")
    kept["date_pkt"] = utc.dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    kept["dist_km"], kept["bearing_deg"] = distance_bearing(kept["latitude"], kept["longitude"])
    kept["ring"] = None
    for name, (lo, hi) in RINGS.items():
        kept.loc[(kept["dist_km"] >= lo) & (kept["dist_km"] < hi), "ring"] = name
    kept["sector"] = None
    within = kept["dist_km"] < MAX_KM
    for name, (lo, hi) in SECTORS.items():
        kept.loc[within & (kept["bearing_deg"] >= lo) & (kept["bearing_deg"] < hi), "sector"] = name
    return kept


def daily_counts(kept: pd.DataFrame, first_day: str, last_day: str) -> pd.DataFrame:
    """Per PKT day: count and FRP sum per ring and sector; days without fires are 0."""
    days = pd.date_range(first_day, last_day, freq="D", name="date")
    out = pd.DataFrame(index=days)
    for col, groups in (("ring", RINGS), ("sector", SECTORS)):
        for g in groups:
            sub = kept[kept[col] == g].groupby("date_pkt")
            out[f"{g}_count"] = sub.size().reindex(days, fill_value=0).astype(int)
            out[f"{g}_frp_mw"] = sub["frp"].sum().reindex(days, fill_value=0.0)
    return out


def previous_week_features(daily: pd.DataFrame, target_week_starts, prefix: str = "fire_prev_") -> pd.DataFrame:
    """For each Monday T: sums over the 7 PKT days of week T−1. NaN if any of those days lies
    outside the downloaded period (not observed), never imputed."""
    rows = []
    first, last = daily.index.min(), daily.index.max()
    for t in pd.DatetimeIndex(target_week_starts):
        if t.day_of_week != 0 or t != t.normalize():
            raise ValueError(f"target week must start on a Monday 00:00, got {t}")
        lo, hi = t - pd.Timedelta(days=7), t - pd.Timedelta(days=1)
        row = {"target_week_start": t}
        covered = lo >= first and hi <= last
        w = daily.loc[lo:hi]
        for c in daily.columns:
            row[prefix + c] = float(w[c].sum()) if covered else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    weekly = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "pm25_weekly_target.csv", parse_dates=["week_start"])
    first_day, last_day = "2019-04-01", "2025-02-28"   # PKT days fully inside the UTC download window
    summaries, daily_by = {}, {}
    for source in (PRIMARY, CROSSCHECK):
        raw = load_source(source)
        kept = prepare(raw)
        kept = kept[(kept["date_pkt"] >= first_day) & (kept["date_pkt"] <= last_day)]
        daily_by[source] = daily_counts(kept, first_day, last_day)
        summaries[source] = {
            "raw_detections": len(raw),
            "kept_vegetation_n_or_h": len(kept),
            "dropped_low_conf": int((raw["confidence"].astype(str) == "l").sum()),
            "dropped_non_vegetation_type": int((raw["type"] != 0).sum()),
            "within_500km": int((kept["dist_km"] < MAX_KM).sum()),
            "by_ring": kept["ring"].value_counts().to_dict(),
            "by_sector": kept["sector"].value_counts().to_dict(),
        }
    d = daily_by[PRIMARY]
    d.to_csv(PROJECT_ROOT / "data" / "processed" / "firms_viirs_snpp_daily_pkt.csv")
    feats = previous_week_features(d, weekly["week_start"])
    feats.to_csv(PROJECT_ROOT / "data" / "processed" / "firms_prev_week_features.csv", index=False)

    # cross-check: weekly totals SNPP vs NOAA-20 (same definitions)
    x = previous_week_features(daily_by[CROSSCHECK], weekly["week_start"], prefix="n20_")
    m = feats.merge(x, on="target_week_start").dropna()
    xcheck = {}
    for g in list(RINGS) + list(SECTORS):
        a, b = m[f"fire_prev_{g}_count"], m[f"n20_{g}_count"]
        xcheck[g] = {"pearson_r_counts": round(float(np.corrcoef(a, b)[0, 1]), 3),
                     "ratio_noaa20_to_snpp": round(float(b.sum() / a.sum()), 3) if a.sum() else None}
    summary = {"sources": summaries, "target_weeks": len(feats),
               "target_weeks_with_features": int(feats.drop(columns="target_week_start").notna().all(axis=1).sum()),
               "feature_columns": [c for c in feats.columns if c.startswith("fire_prev_")],
               "weekly_crosscheck_snpp_vs_noaa20": xcheck}
    print(json.dumps(summary, indent=2, default=str))
    mon = d.groupby(d.index.month)[["r0_100_count", "r100_300_count", "east_se_count", "west_s_count"]].sum()
    print("\nVIIRS SNPP kept detections by calendar month (all years):\n", mon.to_string())


if __name__ == "__main__":
    main()
