"""Stage 1B: hourly QC, 18/24 daily completeness, and repeated-value diagnostics for one
OpenAQ location downloaded by src.download_openaq.

Usage:
    python -m src.run_openaq_coverage --location-id 8664

Outputs:
    data/processed/openaq_{id}_hourly_qc.csv     complete hourly grid with validity/repeat flags
    data/processed/openaq_{id}_daily.csv         daily counts and completeness-gated mean
    results/tables/openaq_{id}_coverage_by_year.csv
    results/tables/openaq_{id}_coverage_by_month.csv
    results/tables/openaq_{id}_weekly_completeness.csv
    results/tables/openaq_{id}_repeats_by_year.csv
    results/tables/openaq_{id}_gaps.csv           runs of >= 7 consecutive incomplete days
    results/tables/openaq_{id}_qc_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src import pm25_qc as qc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GAP_MIN_DAYS = 7


def coverage_by_period(daily: pd.DataFrame, files_per_day: pd.Series, freq: str) -> pd.DataFrame:
    period = daily.index.to_period(freq)
    d = daily.assign(has_file=files_per_day.reindex(daily.index).fillna(0).gt(0))
    g = d.groupby(period)
    out = pd.DataFrame(
        {
            "days_in_record": g.size(),
            "days_with_file": g["has_file"].sum(),
            "days_with_any_valid_hour": g["hours_valid"].apply(lambda s: int((s > 0).sum())),
            "days_complete_18of24": g["complete"].sum(),
            "valid_hours": g["hours_valid"].sum(),
            "expected_hours": g.size() * qc.HOURS_PER_DAY,
        }
    )
    out["pct_days_complete"] = (100 * out["days_complete_18of24"] / out["days_in_record"]).round(1)
    out["pct_hours_valid"] = (100 * out["valid_hours"] / out["expected_hours"]).round(1)
    out.index.name = "year" if freq == "Y" else "month"
    return out


def repeats_by_year(grid: pd.DataFrame) -> pd.DataFrame:
    day = qc.assign_day(grid.index)
    g = grid.assign(year=day.year)
    valid = g[g["valid"]]
    # one row per run of equal consecutive valid values; run starts where repeat_prev is False
    run_starts = valid[~valid["repeat_prev"]]
    by = valid.groupby("year")
    out = pd.DataFrame(
        {
            "valid_hours": by.size(),
            "repeat_hours": by["repeat_prev"].sum(),
            "runs_len_ge_3": run_starts.groupby("year")["repeat_run_length"].apply(lambda s: int((s >= 3).sum())),
            "runs_len_ge_6": run_starts.groupby("year")["repeat_run_length"].apply(lambda s: int((s >= 6).sum())),
            "max_run_length": by["repeat_run_length"].max(),
            "hours_above_review_threshold": by["value_valid"].apply(lambda s: int((s > qc.HIGH_VALUE_REVIEW_THRESHOLD).sum())),
            "hours_equal_zero": by["value_valid"].apply(lambda s: int((s == 0).sum())),
        }
    )
    out["pct_repeat_of_valid"] = (100 * out["repeat_hours"] / out["valid_hours"]).round(1)
    return out


def incomplete_gaps(daily: pd.DataFrame, min_days: int = GAP_MIN_DAYS) -> pd.DataFrame:
    inc = ~daily["complete"]
    run_id = (inc != inc.shift()).cumsum()
    runs = daily.index.to_series()[inc].groupby(run_id[inc]).agg(["min", "max", "size"])
    runs.columns = ["first_incomplete_day", "last_incomplete_day", "n_days"]
    return runs[runs["n_days"] >= min_days].sort_values("first_incomplete_day").reset_index(drop=True)


def weekly_completeness(daily: pd.DataFrame) -> pd.DataFrame:
    """Weeks Monday–Sunday (local); count of complete days per week, tabulated by year."""
    week_start = daily.index.to_period("W-SUN").start_time
    wk = daily.groupby(week_start)["complete"].agg(["sum", "size"])
    wk = wk[wk["size"] == 7]  # drop partial weeks at record ends
    table = pd.crosstab(wk.index.year, wk["sum"].astype(int)).reindex(columns=range(8), fill_value=0)
    table.index.name = "year_of_week_start"
    table.columns = [f"weeks_with_{c}_complete_days" for c in table.columns]
    return table


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--location-id", type=int, required=True)
    args = ap.parse_args()
    lid = args.location_id

    raw_dir = PROJECT_ROOT / "data" / "raw" / "openaq" / f"location_{lid}"
    proc_dir = PROJECT_ROOT / "data" / "processed"
    tab_dir = PROJECT_ROOT / "results" / "tables"
    paths = sorted(raw_dir.rglob("*.csv.gz"))
    if not paths:
        raise SystemExit(f"no files under {raw_dir}; run src.download_openaq first")

    raw = qc.load_openaq_files(paths)
    hourly = qc.parse_hourly(raw)
    hourly, dup_stats = qc.resolve_duplicate_timestamps(hourly)
    grid = qc.flag_repeats(qc.to_complete_hourly_grid(hourly))
    daily = qc.full_day_index(qc.daily_summary(grid))

    file_dates = pd.to_datetime(pd.Series([p.name.split("-")[-1][:8] for p in paths]), format="%Y%m%d")
    files_per_day = file_dates.value_counts()
    file_valid = raw.assign(v=pd.to_numeric(raw["value"], errors="coerce")).groupby("source_file")["v"].apply(lambda s: bool((s >= 0).any()))

    by_year = coverage_by_period(daily, files_per_day, "Y")
    by_month = coverage_by_period(daily, files_per_day, "M")
    reps = repeats_by_year(grid)
    gaps = incomplete_gaps(daily)
    weekly = weekly_completeness(daily)

    proc_dir.mkdir(parents=True, exist_ok=True)
    grid.to_csv(proc_dir / f"openaq_{lid}_hourly_qc.csv")
    daily.to_csv(proc_dir / f"openaq_{lid}_daily.csv")
    by_year.to_csv(tab_dir / f"openaq_{lid}_coverage_by_year.csv")
    by_month.to_csv(tab_dir / f"openaq_{lid}_coverage_by_month.csv")
    reps.to_csv(tab_dir / f"openaq_{lid}_repeats_by_year.csv")
    gaps.to_csv(tab_dir / f"openaq_{lid}_gaps.csv", index=False)
    weekly.to_csv(tab_dir / f"openaq_{lid}_weekly_completeness.csv")

    summary = {
        "location_id": lid,
        "files": len(paths),
        "files_with_no_valid_value": int((~file_valid).sum()),
        "raw_rows": len(raw),
        "parameters": raw["parameter"].value_counts().to_dict(),
        "units": raw["units"].value_counts().to_dict(),
        "location_names": raw["location"].value_counts().to_dict(),
        "sensor_ids": raw["sensors_id"].value_counts().to_dict(),
        "coordinates": raw.groupby(["lat", "lon"]).size().rename("rows").reset_index().to_dict("records"),
        "duplicate_timestamps": dup_stats,
        "hour_label_convention": qc.HOUR_LABEL_CONVENTION,
        "first_timestamp": str(grid.index.min()),
        "last_timestamp": str(grid.index.max()),
        "first_day": str(daily.index.min().date()),
        "last_day": str(daily.index.max().date()),
        "days_in_record": len(daily),
        "days_complete_18of24": int(daily["complete"].sum()),
        "hours_in_grid": len(grid),
        "hours_valid": int(grid["valid"].sum()),
        "hours_repeat_prev": int(grid["repeat_prev"].sum()),
        "valid_value_min": float(grid["value_valid"].min()),
        "valid_value_max": float(grid["value_valid"].max()),
        "gaps_ge_7_incomplete_days": len(gaps),
    }
    (tab_dir / f"openaq_{lid}_qc_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))

    pd.set_option("display.width", 200)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print("\nBY YEAR\n", by_year.to_string())
    print("\nREPEATS\n", reps.to_string())
    print("\nWEEKLY\n", weekly.to_string())
    print("\nGAPS >= 7 incomplete days\n", gaps.to_string())


if __name__ == "__main__":
    main()
