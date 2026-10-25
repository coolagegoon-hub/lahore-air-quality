"""Stage 9a: how often is the trajectory arrival height above ERA5's boundary layer?

Design pre-declared in results/tables/stage9a_blh_predeclaration.md (committed 69de915 before any
Stage 9a code was run). Descriptive frequencies only; nothing in Stages 1–8 changes.

Usage:
    python -m src.stage9a_blh_check
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import era5_features as ef

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage9a"
HEIGHTS = (500, 250, 100)
ARRIVAL_HOUR_PKT = 11               # 06 UTC
FIRST, LAST = "2019-04-01", "2025-02-28"
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "pre-monsoon", 4: "pre-monsoon", 5: "pre-monsoon",
           6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon", 10: "post-monsoon", 11: "post-monsoon"}
ORDER = ["winter", "pre-monsoon", "monsoon", "post-monsoon", "Oct-Jan"]


def with_groups(df: pd.DataFrame, date_col: str) -> list[tuple[str, pd.DataFrame]]:
    """The four seasons plus the secondary October–January split."""
    m = df[date_col].dt.month
    groups = [(s, df[m.map(SEASONS) == s]) for s in ORDER[:4]]
    return groups + [("Oct-Jan", df[m.isin([10, 11, 12, 1])])]


def share_below(blh: pd.Series, heights=HEIGHTS) -> dict:
    return {f"pct_below_{h}m": float(100 * (blh < h).mean()) for h in heights}


def summarise(hourly: pd.DataFrame, days: pd.DataFrame) -> pd.DataFrame:
    """hourly: columns day (PKT date), hour_pkt, blh_m. days: Stage 7 analysis days (date, season, pm25)."""
    h = hourly[(hourly["day"] >= FIRST) & (hourly["day"] <= LAST)]
    arr = h[h["hour_pkt"] == ARRIVAL_HOUR_PKT]
    d = days.merge(arr[["day", "blh_m"]], left_on="date", right_on="day", how="inner")
    rows = []
    for (name, gh), (_, ga), (_, gd) in zip(with_groups(h, "day"), with_groups(arr, "day"), with_groups(d, "date")):
        row = {"group": name, "n_hours": len(gh), **{f"all_hours_{k}": v for k, v in share_below(gh["blh_m"]).items()},
               "n_days_0600utc": len(ga), **{f"arrival_{k}": v for k, v in share_below(ga["blh_m"]).items()},
               "median_blh_0600utc_m": float(ga["blh_m"].median()),
               "iqr_low_m": float(ga["blh_m"].quantile(0.25)), "iqr_high_m": float(ga["blh_m"].quantile(0.75))}
        if name != "Oct-Jan" and len(gd) >= 3:   # terciles within season (pre-declared per season)
            terc = pd.qcut(gd["pm25_daily_mean"], 3, labels=["low", "mid", "high"])
            for t in ("low", "high"):
                sub = gd[terc == t]
                row[f"pm_{t}_third_n_days"] = len(sub)
                row[f"pm_{t}_third_pct_below_500m_0600utc"] = float(100 * (sub["blh_m"] < 500).mean())
        rows.append(row)
    return pd.DataFrame(rows).round(1)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    h = ef.to_hourly_pkt(ef.load_raw())
    hourly = pd.DataFrame({"day": h["day_instant"], "hour_pkt": h["time_pkt"].dt.hour, "blh_m": h["blh_m"]})
    days = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage7" / "analysis_days.csv", parse_dates=["date"])
    out = summarise(hourly, days[["date", "pm25_daily_mean"]])
    out.to_csv(OUT_DIR / "blh_below_arrival_height.csv", index=False)
    info = {"predeclaration": "results/tables/stage9a_blh_predeclaration.md", "period": [FIRST, LAST],
            "arrival_hour_pkt": ARRIVAL_HOUR_PKT, "missing_blh_hours": int(hourly["blh_m"].isna().sum()),
            "analysis_days": len(days)}
    (OUT_DIR / "stage9a_summary.json").write_text(json.dumps(info, indent=2))
    pd.set_option("display.width", 250)
    print(json.dumps(info, indent=2))
    print(out.T.to_string())


if __name__ == "__main__":
    main()
