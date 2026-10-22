"""Simplified one-box mass-balance features from ERA5 (previous week only).

One-box model: a box over the city with along-wind length L, height H (boundary-layer height)
and wind speed u through it. With a constant surface emission flux q, the steady-state
concentration is C_ss = q·L / (u·H). For fixed q and L this is proportional to 1/(u·H), the
inverse of the ventilation coefficient VC = H·u (m² s⁻¹). The flushing (residence) time of air in
the box is tau = L/u.

Features for target week T (Monday–Sunday, PKT) use ONLY the hourly ERA5 values of the 7 PKT days
of week T−1 (hours assigned to PKT dates as in src.era5_features):
    mb_prev_vc_mean          mean hourly VC (m² s⁻¹)
    mb_prev_vc_night_mean    mean hourly VC over night hours (PKT 18:00–05:59)
    mb_prev_css_index        mean hourly 1/max(VC, VC_FLOOR), × 1000 (s m⁻², scaled); the
                             one-box concentration index per unit (q·L)
    mb_prev_flush_hours      median hourly flushing time L / max(u, U_FLOOR) (hours)
    mb_prev_low_vent_hours   hours with VC < LOW_VC
Assumptions (documented, not literature values, fixed before any modelling results):
- u = 10 m wind speed; H = ERA5 boundary-layer height.
- L = BOX_LENGTH_KM (30 km, approximate extent of Lahore); only scales the flushing time.
- Floors VC_FLOOR = 10 m² s⁻¹ and U_FLOOR = 0.1 m s⁻¹ avoid division by ~0 in calm hours.
- LOW_VC = 1000 m² s⁻¹ is a project-defined "low ventilation" threshold.
- Emissions q are unknown and NOT modelled; the features describe dispersion only. Past PM2.5
  and fire activity enter the model separately.
- Same availability caveat as src.era5_features: ERA5 stands in for operational analyses.

Usage:
    python -m src.mass_balance_features
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import era5_features as ef

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOX_LENGTH_KM = 30.0
VC_FLOOR = 10.0
U_FLOOR = 0.1
LOW_VC = 1000.0
NIGHT_HOURS = set(range(18, 24)) | set(range(0, 6))


def hourly_box(h: pd.DataFrame) -> pd.DataFrame:
    """Hourly ventilation coefficient, box index and flushing time from src.era5_features.to_hourly_pkt output."""
    b = pd.DataFrame({"day": h["day_instant"], "hour_pkt": h["time_pkt"].dt.hour})
    b["vc"] = h["blh_m"] * h["ws10"]
    b["css_index"] = 1000.0 / np.maximum(b["vc"], VC_FLOOR)
    b["flush_hours"] = (BOX_LENGTH_KM * 1000.0 / np.maximum(h["ws10"], U_FLOOR)) / 3600.0
    b["low_vent"] = b["vc"] < LOW_VC
    b["night"] = b["hour_pkt"].isin(NIGHT_HOURS)
    return b


def previous_week_features(b: pd.DataFrame, target_week_starts) -> pd.DataFrame:
    """One row per target week T from the hours of the 7 PKT days of week T−1 only.
    All features are NaN unless all 7 × 24 hours are present (no imputation)."""
    rows = []
    for t in pd.DatetimeIndex(target_week_starts):
        if t.dayofweek != 0 or t != t.normalize():
            raise ValueError(f"target week must start on a Monday 00:00, got {t}")
        w = b[(b["day"] >= t - pd.Timedelta(days=7)) & (b["day"] < t)]
        row = {"target_week_start": t, "mb_hours": len(w)}
        ok = len(w) == 7 * 24
        row["mb_prev_vc_mean"] = w["vc"].mean() if ok else np.nan
        row["mb_prev_vc_night_mean"] = w.loc[w["night"], "vc"].mean() if ok else np.nan
        row["mb_prev_css_index"] = w["css_index"].mean() if ok else np.nan
        row["mb_prev_flush_hours"] = w["flush_hours"].median() if ok else np.nan
        row["mb_prev_low_vent_hours"] = float(w["low_vent"].sum()) if ok else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    h = ef.to_hourly_pkt(ef.load_raw())
    b = hourly_box(h)
    weekly = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "pm25_weekly_target.csv", parse_dates=["week_start"])
    feats = previous_week_features(b, weekly["week_start"])
    feats.to_csv(PROJECT_ROOT / "data" / "processed" / "mass_balance_prev_week_features.csv", index=False)

    # plausibility: monthly medians of hourly VC, and association with the NEXT week's PM2.5
    m = b.groupby(b["day"].dt.month).agg(vc_median=("vc", "median"), low_vent_share=("low_vent", "mean"),
                                         flush_h_median=("flush_hours", "median")).round(2)
    joined = feats.merge(weekly[["week_start", "weekly_mean_observed_days", "eligible"]],
                         left_on="target_week_start", right_on="week_start")
    j = joined[joined["eligible"]]
    rho = {c: round(float(j[c].corr(j["weekly_mean_observed_days"], method="spearman")), 3)
           for c in feats.columns if c.startswith("mb_prev_")}
    summary = {"target_weeks": len(feats), "weeks_with_features": int(feats["mb_hours"].eq(168).sum()),
               "box_length_km": BOX_LENGTH_KM, "vc_floor": VC_FLOOR, "u_floor": U_FLOOR, "low_vc": LOW_VC,
               "spearman_with_target_week_pm25_eligible_weeks_DESCRIPTIVE_ONLY": rho, "n_eligible_weeks": len(j)}
    print(json.dumps(summary, indent=2))
    print("\nMonthly hourly ventilation (all years):\n", m.to_string())


if __name__ == "__main__":
    main()
