"""Build the Lahore hourly PM2.5 series from cached AirNow archive lines (AQS 586PK3010003),
apply the 18/24 daily rule, and compare it with OpenAQ 8664 and AirNow's own daily values.

Conventions
- Source: AirNow ``HourlyData_YYYYMMDDhh.dat`` lines extracted by src.airnow_bulk (cached under
  data/raw/airnow_files/). Per the AirNow Hourly Data File fact sheet (Aug 2025) the time is GMT
  and marks the BEGINNING of the 1-hour averaging period.
- Output time: PKT (Asia/Karachi, UTC+05:00, no DST), HOUR-ENDING: begin GMT + 1 h, converted
  to PKT. A local day is hour-ending 01:00 ... 00:00 (next day), i.e. begin-hours 00:00 ... 23:00,
  which is also AirNow's own daily definition ("midnight-to-midnight, begin-hour, local standard
  time"). Day assignment and the 18/24 rule reuse src.pm25_qc unchanged.
- Validity: a record present in AirNow is valid unless its value is negative. AirNow keeps small
  negatives (typically > -5) as valid; this project's QC rule (src.pm25_qc) treats negatives as
  invalid. ``negative_policy`` selects: "invalid" (default, project rule) or "keep_ge_minus5".
  Hours with no AirNow record are missing. Nothing is imputed.

Usage:
    python -m src.airnow_hourly_series
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import airnow_archive as aa
from src import pm25_qc as qc
from src import stage1c_analysis as s1c

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AQSID = "586PK3010003"
FIRST_LOCAL_DAY = "2019-05-22"
LAST_LOCAL_DAY = "2025-02-18"
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "airnow_rebuild"
NEGATIVE_POLICIES = ("invalid", "keep_ge_minus5")


def local_hour_ending_range(first_day: str, last_day: str) -> pd.DatetimeIndex:
    """All hour-ending PKT labels covering local days first_day..last_day inclusive."""
    start = pd.Timestamp(first_day, tz=qc.TZ) + pd.Timedelta(hours=1)
    end = pd.Timestamp(last_day, tz=qc.TZ) + pd.Timedelta(days=1)
    return pd.date_range(start, end, freq="h", name="timestamp")


def gmt_dates_for_local_days(first_day: str, last_day: str) -> tuple[str, str]:
    """GMT archive dates whose files cover the local days (PKT = GMT + 5)."""
    rng = local_hour_ending_range(first_day, last_day)
    begins_utc = (rng - pd.Timedelta(hours=1)).tz_convert("UTC")
    return begins_utc.min().strftime("%Y-%m-%d"), begins_utc.max().strftime("%Y-%m-%d")


def validate_airnow_rows(df: pd.DataFrame, aqsid: str = AQSID) -> pd.DataFrame:
    """Keep this site's PM2.5 rows; raise on anything unexpected rather than guessing."""
    df = df[(df["aqsid"] == aqsid) & (df["parameter"] == "PM2.5")].copy()
    problems = []
    if set(df["units"].unique()) - {"UG/M3"}:
        problems.append(f"units {sorted(df['units'].unique())}")
    if set(df["gmt_offset"].astype(str).unique()) - {"5"}:
        problems.append(f"gmt_offset {sorted(df['gmt_offset'].astype(str).unique())}")
    if df["value"].isna().any():
        problems.append(f"{int(df['value'].isna().sum())} non-numeric values")
    if df["period_begin_utc"].duplicated().any():
        problems.append(f"{int(df['period_begin_utc'].duplicated().sum())} duplicate hours")
    if problems:
        raise ValueError("unexpected AirNow rows: " + "; ".join(problems))
    return df


def to_hourly(df: pd.DataFrame, negative_policy: str = "invalid") -> pd.DataFrame:
    """Index AirNow rows by hour-ending PKT and set validity per ``negative_policy``."""
    if negative_policy not in NEGATIVE_POLICIES:
        raise ValueError(f"negative_policy must be one of {NEGATIVE_POLICIES}")
    out = pd.DataFrame({"value": df["value"].to_numpy()},
                       index=pd.DatetimeIndex(df["period_end_local"], name="timestamp").tz_convert(qc.TZ))
    floor = 0.0 if negative_policy == "invalid" else -5.0
    out["valid"] = out["value"] >= floor
    return out.sort_index()


def complete_grid(hourly: pd.DataFrame, labels: pd.DatetimeIndex) -> pd.DataFrame:
    """Reindex to explicit hour-ending labels (absent hours become explicit invalid rows), then
    add src.pm25_qc's repeat flags. Columns match src.pm25_qc.to_complete_hourly_grid."""
    g = hourly[["value", "valid"]].reindex(labels)
    g["valid"] = g["valid"].fillna(False).astype(bool)
    g["present_in_source"] = hourly.index.to_series().reindex(labels).notna().to_numpy()
    g["value_valid"] = g["value"].where(g["valid"])
    return qc.flag_repeats(g)


def build(negative_policy: str = "invalid", first_day: str = FIRST_LOCAL_DAY, last_day: str = LAST_LOCAL_DAY,
          aqsid: str = AQSID) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    start, end = gmt_dates_for_local_days(first_day, last_day)
    raw = aa.hourly(aqsid, start, end)
    if raw.attrs.get("files_missing"):
        raise RuntimeError(f"{raw.attrs['files_missing']} archive files missing from cache; run src.airnow_bulk")
    rows = validate_airnow_rows(raw, aqsid)
    labels = local_hour_ending_range(first_day, last_day)
    hourly = to_hourly(rows, negative_policy)
    grid = complete_grid(hourly.loc[hourly.index.isin(labels)], labels)
    daily = qc.daily_summary(grid)
    info = {
        "negative_policy": negative_policy,
        "gmt_files_from": start, "gmt_files_to": end,
        "rows_in_range": int(hourly.index.isin(labels).sum()),
        "negative_values_in_range": int((hourly.loc[hourly.index.isin(labels), "value"] < 0).sum()),
    }
    return grid, daily, info


# ---------------------------------------------------------------- comparisons

def compare_with_airnow_daily(daily: pd.DataFrame, airnow_daily: pd.DataFrame) -> pd.DataFrame:
    """Rebuilt daily means vs AirNow's own PM2.5-24hr values, under the project day convention
    and under the alternative (hour-ending label's calendar date) as a check of the time handling."""
    an = airnow_daily.set_index(pd.to_datetime(airnow_daily["date"]))["value"]
    m = pd.concat([daily[["hours_valid", "mean_all_valid_hours", "pm25_daily_mean"]], an.rename("airnow_daily")],
                  axis=1, sort=True).loc[daily.index]
    return m


def alternative_day_means(grid: pd.DataFrame) -> pd.Series:
    """Daily means if hours were grouped by the calendar date of their hour-ending label."""
    return grid["value_valid"].groupby(grid.index.tz_localize(None).normalize()).mean()


def monthly_alignment(openaq_valid: pd.Series, airnow_valid: pd.Series) -> pd.DataFrame:
    """Per local month: % of OpenAQ hours equal (±MATCH_TOL) to AirNow at lag 0 and +1 h."""
    month = openaq_valid.index.tz_localize(None).to_period("M")
    rows = []
    for mth, idx in openaq_valid.groupby(month).groups.items():
        o = openaq_valid.loc[idx]
        lo, hi = o.index.min() - pd.Timedelta(hours=3), o.index.max() + pd.Timedelta(hours=3)
        a = airnow_valid.loc[lo:hi]
        lags = s1c.lag_alignment(o, a, lags=(0, 1)).set_index("lag_h")
        p0, p1 = lags.at[0, "pct_equal"], lags.at[1, "pct_equal"]
        pairs = int(lags.at[0, "pairs"])
        if pairs < 24:
            label = "too_few_pairs"
        elif p0 >= 90:
            label = "aligned"
        elif p1 >= 90:
            label = "shifted_1h_early"
        else:
            label = "mixed"
        rows.append({"month": str(mth), "pairs": pairs, "pct_equal_lag0": p0, "pct_equal_lag_plus1": p1, "label": label})
    return pd.DataFrame(rows).set_index("month")


def coverage_tables(daily_by_source: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    by_year, by_season, weekly_year, weekly_season = [], [], [], []
    for name, d in daily_by_source.items():
        y = d.groupby(d.index.year).agg(days=("complete", "size"), complete_days=("complete", "sum"),
                                         valid_hours=("hours_valid", "sum"))
        y["pct_days_complete"] = (100 * y.complete_days / y.days).round(1)
        y["pct_hours_valid"] = (100 * y.valid_hours / (24 * y.days)).round(1)
        by_year.append(y.add_prefix(f"{name}_"))
        sm = d[d.index.month.isin(s1c.SMOG_MONTHS)]
        season = np.where(sm.index.month == 1, sm.index.year - 1, sm.index.year)
        lab = [f"{s}-{str(s + 1)[2:]}" for s in season]
        s = sm.groupby(lab).agg(days=("complete", "size"), complete_days=("complete", "sum"))
        by_season.append(s.add_prefix(f"{name}_"))
        wk = s1c.weekly_completeness(d)
        weekly_year.append(s1c.weekly_threshold_counts(wk, "year").add_prefix(f"{name}_"))
        weekly_season.append(s1c.weekly_threshold_counts(wk, "smog_season").add_prefix(f"{name}_"))
    return {
        "coverage_by_year": pd.concat(by_year, axis=1),
        "coverage_by_smog_season": pd.concat(by_season, axis=1),
        "weekly_counts_by_year": pd.concat(weekly_year, axis=1),
        "weekly_counts_by_smog_season": pd.concat(weekly_season, axis=1),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)

    grid, daily, info = build("invalid")
    grid_k, daily_k, info_k = build("keep_ge_minus5")
    grid.to_csv(PROJECT_ROOT / "data" / "processed" / f"airnow_{AQSID}_hourly.csv")
    daily.to_csv(PROJECT_ROOT / "data" / "processed" / f"airnow_{AQSID}_daily_18of24.csv")

    # OpenAQ 8664 over the same local days (Stage 1B pipeline, unchanged)
    oq_grid = s1c.build_openaq_grid()
    oq_daily = qc.full_day_index(qc.daily_summary(oq_grid)).loc[FIRST_LOCAL_DAY:LAST_LOCAL_DAY]
    oq_daily = oq_daily.reindex(daily.index).fillna({"hours_valid": 0, "complete": False}).astype({"complete": bool})

    # 1. rebuild vs AirNow's own daily values
    an_daily = pd.read_csv(PROJECT_ROOT / "data" / "processed" / f"airnow_{AQSID}_daily.csv")
    cmp_an = compare_with_airnow_daily(daily, an_daily)
    alt = alternative_day_means(grid).reindex(cmp_an.index)
    both = cmp_an.dropna(subset=["airnow_daily", "mean_all_valid_hours"])
    d_proj = (both.mean_all_valid_hours - both.airnow_daily)
    d_alt = (alt.loc[both.index] - both.airnow_daily)
    an_check = {
        "days_both": len(both),
        "project_convention_mean_abs_diff": round(float(d_proj.abs().mean()), 3),
        "project_convention_pct_within_0.5": round(float(100 * (d_proj.abs() <= 0.5).mean()), 1),
        "alternative_convention_mean_abs_diff": round(float(d_alt.abs().mean()), 3),
        "alternative_convention_pct_within_0.5": round(float(100 * (d_alt.abs() <= 0.5).mean()), 1),
        "min_hours_valid_on_days_airnow_reports": int(both.hours_valid.min()),
        "airnow_daily_days_with_<18_rebuilt_hours": int((both.hours_valid < 18).sum()),
        "rebuilt_complete_days_without_airnow_daily": int((cmp_an.pm25_daily_mean.notna() & cmp_an.airnow_daily.isna()).sum()),
    }
    hours_hist = both.hours_valid.value_counts().sort_index()
    cmp_an.to_csv(OUT_DIR / "rebuild_vs_airnow_daily.csv")
    hours_hist.rename("days").to_csv(OUT_DIR / "airnow_daily_reported_by_rebuilt_hours.csv")

    # 2. vs OpenAQ: hourly alignment by month, and daily means on common complete days
    align = monthly_alignment(oq_grid["value_valid"].dropna(), grid["value_valid"].dropna())
    align.to_csv(OUT_DIR / "openaq_alignment_by_month.csv")
    common = daily.complete & oq_daily.complete
    dd = (oq_daily.loc[common, "pm25_daily_mean"] - daily.loc[common, "pm25_daily_mean"])
    oq_cmp = {
        "common_complete_days": int(common.sum()),
        "airnow_complete_only": int((daily.complete & ~oq_daily.complete).sum()),
        "openaq_complete_only": int((~daily.complete & oq_daily.complete).sum()),
        "mean_diff_openaq_minus_airnow": round(float(dd.mean()), 3),
        "mean_abs_diff": round(float(dd.abs().mean()), 3),
        "max_abs_diff": round(float(dd.abs().max()), 2),
        "pearson_r": round(float(oq_daily.loc[common, "pm25_daily_mean"].corr(daily.loc[common, "pm25_daily_mean"])), 5),
    }
    only_oq = daily.index[~daily.complete & oq_daily.complete]
    pd.DataFrame({"airnow_hours_valid": daily.loc[only_oq, "hours_valid"], "openaq_hours_valid": oq_daily.loc[only_oq, "hours_valid"],
                  "openaq_daily_mean": oq_daily.loc[only_oq, "pm25_daily_mean"]}).to_csv(OUT_DIR / "days_complete_in_openaq_only.csv")

    # 3. coverage, both sources and the negative-value sensitivity
    tabs = coverage_tables({"airnow": daily, "airnow_keepneg": daily_k, "openaq": oq_daily})
    for k, t in tabs.items():
        t.to_csv(OUT_DIR / f"{k}.csv")

    # 4. repeated values in the original source
    runs = s1c.repeat_runs(grid)
    runs.to_csv(OUT_DIR / "airnow_repeat_runs.csv", index=False)
    run_summary = runs.groupby("year").agg(runs=("length_h", "size"), max_len=("length_h", "max"),
                                           runs_ge6=("length_h", lambda s: int((s >= 6).sum())))
    run_summary["repeat_pct_of_valid_hours"] = (100 * grid.groupby(qc.assign_day(grid.index).year)["repeat_prev"].sum()
                                                 / grid.groupby(qc.assign_day(grid.index).year)["valid"].sum()).round(1)
    run_summary.to_csv(OUT_DIR / "airnow_repeat_summary_by_year.csv")

    summary = {
        "info": info, "info_keep_negatives": info_k,
        "local_days": len(daily), "hours_in_grid": len(grid),
        "airnow_valid_hours": int(grid.valid.sum()), "airnow_complete_days": int(daily.complete.sum()),
        "airnow_keepneg_complete_days": int(daily_k.complete.sum()),
        "openaq_valid_hours_same_days": int(oq_grid.loc[grid.index.min():grid.index.max(), "valid"].sum()),
        "openaq_complete_days_same_days": int(oq_daily.complete.sum()),
        "first_valid_hour": str(grid.index[grid.valid].min()), "last_valid_hour": str(grid.index[grid.valid].max()),
        "rebuild_vs_airnow_daily": an_check, "vs_openaq_daily": oq_cmp,
        "alignment_month_labels": align.label.value_counts().to_dict(),
        "airnow_runs_ge6": runs[runs.length_h >= 6][["first_hour_end", "last_hour_end", "length_h", "value"]].astype(str).to_dict("records"),
    }
    (OUT_DIR / "airnow_rebuild_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    for title, t in [("AIRNOW DAILY REPORTED BY REBUILT HOURS", hours_hist), ("ALIGNMENT BY MONTH", align),
                     ("REPEATS", run_summary)] + [(k.upper(), t) for k, t in tabs.items()]:
        print(f"\n=== {title}\n{t.to_string()}")


if __name__ == "__main__":
    main()
