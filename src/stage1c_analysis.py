"""Stage 1C: repeated-value runs, exclusion sensitivity, OpenAQ-vs-AirNow comparison and
weekly-target completeness for OpenAQ location 8664 (US Diplomatic Post: Lahore).

Builds on src.pm25_qc (unchanged). Nothing is deleted: exclusion scenarios mark hours invalid
in copies of the hourly grid, and every scenario is reported side by side.

Scenarios
- S0_unflagged:  hourly data as in Stage 1B (only missing / negative values invalid).
- S6_runs_ge6:   additionally invalidate every hour of any run of >= 6 consecutive identical
                 valid values (the whole run, including its first hour).
- S7_runs_ge7:   same with >= 7.

Weeks are Monday-Sunday in local time (PKT). A week's year and smog season are assigned by
its Thursday (ISO-8601 style); the smog season "2019-20" is October 2019 - January 2020.

Usage:
    python -m src.stage1c_analysis
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import airnow_archive as aa
from src import pm25_qc as qc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCATION_ID = 8664
AIRNOW_AQSID = "586PK3010003"
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage1c"
SCENARIOS = {"S0_unflagged": None, "S6_runs_ge6": 6, "S7_runs_ge7": 7}
WEEK_THRESHOLDS = (7, 6, 5)
SMOG_MONTHS = (10, 11, 12, 1)
# Values are treated as the same measurement when they differ by <= this amount. AirNow reports
# some 2019 values to 0.1 ug/m3 and OpenAQ differs from them by exactly 0.1 (rounding).
MATCH_TOL = 0.15
# GMT start dates of the 8-day AirNow hourly windows fetched for comparison
AIRNOW_HOURLY_WINDOWS = [
    "2019-07-09", "2019-11-09", "2020-01-09", "2020-07-09", "2020-11-09", "2021-01-09",
    "2021-07-09", "2021-11-09", "2022-01-09", "2022-11-09", "2023-01-09", "2023-07-09",
    "2023-11-09", "2024-01-09", "2024-07-09", "2024-11-09", "2025-01-09", "2024-05-30",
]


# ---------------------------------------------------------------- hourly grid and runs

def build_openaq_grid(location_id: int = LOCATION_ID) -> pd.DataFrame:
    """Rebuild the Stage 1B hourly grid from the raw files (same code path as Stage 1B)."""
    raw_dir = PROJECT_ROOT / "data" / "raw" / "openaq" / f"location_{location_id}"
    raw = qc.load_openaq_files(sorted(raw_dir.rglob("*.csv.gz")))
    hourly, _ = qc.resolve_duplicate_timestamps(qc.parse_hourly(raw))
    return qc.flag_repeats(qc.to_complete_hourly_grid(hourly))


def repeat_runs(grid: pd.DataFrame, min_length: int = 2) -> pd.DataFrame:
    """One row per run of >= min_length consecutive identical valid hourly values.

    Timestamps are OpenAQ hour-ending labels (PKT). ``first_hour_start`` is the start of the
    first hour's averaging period.
    """
    valid = grid[grid["valid"]]
    run_id = (~grid["repeat_prev"]).cumsum()[grid["valid"]]
    g = valid.groupby(run_id)
    runs = pd.DataFrame(
        {
            "first_hour_end": g.apply(lambda d: d.index.min()),
            "last_hour_end": g.apply(lambda d: d.index.max()),
            "length_h": g.size(),
            "value": g["value_valid"].first(),
        }
    )
    runs = runs[runs["length_h"] >= min_length].reset_index(drop=True)
    runs["first_hour_start"] = runs["first_hour_end"] - pd.Timedelta(hours=1)
    runs["first_day"] = qc.assign_day(pd.DatetimeIndex(runs["first_hour_end"]))
    runs["last_day"] = qc.assign_day(pd.DatetimeIndex(runs["last_hour_end"]))
    runs["year"] = runs["first_day"].dt.year
    return runs


def exclude_runs(grid: pd.DataFrame, min_length: int | None) -> pd.DataFrame:
    """Copy of grid with every hour of runs >= min_length marked invalid (None = no change)."""
    out = grid.copy()
    out["excluded_by_run_rule"] = False
    if min_length is not None:
        mask = out["valid"] & (out["repeat_run_length"] >= min_length)
        out["excluded_by_run_rule"] = mask
        out.loc[mask, "valid"] = False
        out["value_valid"] = out["value"].where(out["valid"])
    return out


def scenario_daily(grid: pd.DataFrame) -> pd.DataFrame:
    return qc.full_day_index(qc.daily_summary(grid))


def run_daily_impacts(runs: pd.DataFrame, daily_by_scenario: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Daily means of every day touched by a run, under each scenario."""
    rows = []
    for i, r in runs.iterrows():
        for day in pd.date_range(r["first_day"], r["last_day"], freq="D"):
            row = {"run_index": i, "date": day, "run_length_h": r["length_h"], "run_value": r["value"]}
            for name, d in daily_by_scenario.items():
                row[f"{name}_hours_valid"] = int(d.at[day, "hours_valid"])
                row[f"{name}_daily_mean"] = d.at[day, "pm25_daily_mean"]
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- weekly target

def weekly_completeness(daily: pd.DataFrame) -> pd.DataFrame:
    """Full Monday-Sunday weeks with complete-day counts, Thursday-based year and season."""
    week_start = daily.index.to_period("W-SUN").start_time
    wk = daily.groupby(week_start).agg(
        days=("complete", "size"),
        complete_days=("complete", "sum"),
        weekly_mean_of_complete_days=("pm25_daily_mean", "mean"),
    )
    wk = wk[wk["days"] == 7].drop(columns="days")
    thursday = wk.index + pd.Timedelta(days=3)
    wk["year"] = thursday.year
    smog = thursday.month.isin(SMOG_MONTHS)
    season_start = np.where(thursday.month == 1, thursday.year - 1, thursday.year)
    wk["smog_season"] = np.where(smog, [f"{y}-{str(y + 1)[2:]}" for y in season_start], "")
    wk.index.name = "week_start"
    return wk


def weekly_threshold_counts(wk: pd.DataFrame, by: str) -> pd.DataFrame:
    sub = wk if by == "year" else wk[wk["smog_season"] != ""]
    g = sub.groupby(by)
    out = pd.DataFrame({"full_weeks": g.size()})
    for t in WEEK_THRESHOLDS:
        out[f"weeks_ge_{t}_of_7"] = g["complete_days"].apply(lambda s, t=t: int((s >= t).sum()))
    return out


def missing_day_error(daily: pd.DataFrame, wk: pd.DataFrame, drop_counts=(1, 2)) -> pd.DataFrame:
    """Exhaustive drop-k-days experiment on 7/7 weeks: error of the mean of the remaining days.

    Assumes missing days are a random subset of the week (missing-at-random); real outages may
    cluster in particular conditions, so this is a lower bound on the uncertainty.
    """
    full = wk[wk["complete_days"] == 7]
    rows = []
    for ws, w in full.iterrows():
        vals = daily.loc[ws: ws + pd.Timedelta(days=6), "pm25_daily_mean"].to_numpy()
        true_mean = vals.mean()
        for k in drop_counts:
            for drop in itertools.combinations(range(7), k):
                kept = np.delete(vals, drop)
                err = kept.mean() - true_mean
                rows.append({"week_start": ws, "smog": w["smog_season"] != "", "days_missing": k,
                             "true_mean": true_mean, "error": err, "abs_pct_error": 100 * abs(err) / true_mean})
    e = pd.DataFrame(rows)
    summary = e.groupby(["days_missing", "smog"]).agg(
        n_weeks=("week_start", "nunique"),
        n_subsets=("error", "size"),
        mean_abs_error_ugm3=("error", lambda s: s.abs().mean()),
        median_abs_pct_error=("abs_pct_error", "median"),
        p95_abs_pct_error=("abs_pct_error", lambda s: s.quantile(0.95)),
        max_abs_pct_error=("abs_pct_error", "max"),
    )
    return summary.round(2)


# ---------------------------------------------------------------- AirNow comparison

def airnow_hourly_series(windows=AIRNOW_HOURLY_WINDOWS, aqsid: str = AIRNOW_AQSID) -> tuple[pd.Series, pd.Series]:
    """AirNow hourly values indexed by hour-ending local time, plus a Series mapping every hour
    covered by the fetched archive files to its window label (so a missing record can be
    distinguished from an hour that was never fetched)."""
    vals, covered = [], []
    for start in windows:
        end = (pd.Timestamp(start) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        df = aa.hourly(aqsid, start, end)
        df = df[df["parameter"] == "PM2.5"]
        vals.append(df.set_index("period_end_local")["value"])
        begins = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(hours=23), freq="h")
        ends_local = (begins + pd.Timedelta(hours=1)).tz_convert(qc.TZ)
        covered.append(pd.Series(start, index=ends_local))
    s = pd.concat(vals)
    s = s[~s.index.duplicated()].sort_index()
    cov = pd.concat(covered)
    cov = cov[~cov.index.duplicated()].sort_index()
    return s, cov


def lag_alignment(openaq: pd.Series, airnow: pd.Series, lags=range(-2, 3)) -> pd.DataFrame:
    """Share of exactly equal values when AirNow is shifted by k hours relative to OpenAQ labels."""
    rows = []
    for k in lags:
        shifted = airnow.copy()
        shifted.index = shifted.index - pd.Timedelta(hours=k)
        both = pd.concat([openaq.rename("o"), shifted.rename("a")], axis=1, join="inner").dropna()
        eq = (both.o - both.a).abs() <= MATCH_TOL
        rows.append({"lag_h": k, "pairs": len(both), "equal_within_tol": int(eq.sum()),
                     "pct_equal": round(100 * eq.mean(), 1) if len(both) else np.nan})
    return pd.DataFrame(rows)


def hourly_comparison(grid: pd.DataFrame, airnow: pd.Series, covered_windows: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hour-by-hour comparison over the covered hours; returns per-hour table and per-window summary."""
    covered = covered_windows.index
    h = pd.DataFrame(index=covered)
    h["openaq"] = grid["value_valid"].reindex(covered)
    h["openaq_repeat_prev"] = grid["repeat_prev"].reindex(covered).fillna(False).astype(bool)
    h["airnow"] = airnow.reindex(covered)
    h["airnow_prev"] = airnow.reindex(covered - pd.Timedelta(hours=1)).to_numpy()
    h["airnow_repeat_prev"] = h["airnow"].notna() & (h["airnow"] == h["airnow_prev"])
    h["airnow_next"] = airnow.reindex(covered + pd.Timedelta(hours=1)).to_numpy()
    o, a = h["openaq"].notna(), h["airnow"].notna()
    close = lambda x, y: (x - y).abs() <= MATCH_TOL  # noqa: E731
    h["category"] = np.select(
        [o & a & close(h.openaq, h.airnow), o & a, o & ~a, ~o & a],
        ["equal", "different", "openaq_only", "airnow_only"],
        default="neither",
    )
    diff = h["category"] == "different"
    h["openaq_equals_airnow_prev_hour"] = diff & close(h.openaq, h.airnow_prev)
    h["openaq_equals_airnow_next_hour"] = diff & close(h.openaq, h.airnow_next)
    h["window"] = covered_windows.to_numpy()

    def summarise(x: pd.DataFrame) -> pd.Series:
        both = x[x.category.isin(["equal", "different"])]
        return pd.Series({
            "hours": len(x),
            "airnow_present": int(x.airnow.notna().sum()),
            "openaq_valid": int(x.openaq.notna().sum()),
            "both": len(both),
            "equal": int((x.category == "equal").sum()),
            "different": int((x.category == "different").sum()),
            "different_and_equal_to_airnow_prev_hour": int(x.openaq_equals_airnow_prev_hour.sum()),
            "different_and_equal_to_airnow_next_hour": int(x.openaq_equals_airnow_next_hour.sum()),
            "openaq_only": int((x.category == "openaq_only").sum()),
            "airnow_only": int((x.category == "airnow_only").sum()),
            "openaq_repeat_pct": round(100 * x.openaq_repeat_prev.sum() / max(x.openaq.notna().sum(), 1), 1),
            "airnow_repeat_pct": round(100 * x.airnow_repeat_prev.sum() / max(x.airnow.notna().sum(), 1), 1),
            "mean_abs_diff_ugm3": round((both.openaq - both.airnow).abs().mean(), 2) if len(both) else np.nan,
        })

    return h, h.groupby("window").apply(summarise)


def daily_comparison(daily_by_scenario: dict[str, pd.DataFrame], airnow_daily: pd.DataFrame) -> pd.DataFrame:
    """Per scenario and year: OpenAQ complete-day means vs AirNow PM2.5-24hr values."""
    an = airnow_daily.set_index("date")["value"].rename("airnow")
    rows = []
    for name, d in daily_by_scenario.items():
        m = pd.concat([d["pm25_daily_mean"].rename("openaq"), an], axis=1, sort=True)
        m = m.loc[d.index.min(): d.index.max()]
        for year, x in m.groupby(m.index.year):
            both = x.dropna()
            diff = both.openaq - both.airnow  # noqa: F841 (daily comparison uses exact differences)
            rows.append({
                "scenario": name, "year": year,
                "airnow_days": int(x.airnow.notna().sum()),
                "openaq_complete_days": int(x.openaq.notna().sum()),
                "both": len(both),
                "openaq_complete_airnow_absent": int((x.openaq.notna() & x.airnow.isna()).sum()),
                "airnow_present_openaq_incomplete": int((x.airnow.notna() & x.openaq.isna()).sum()),
                "mean_diff_ugm3": round(diff.mean(), 2) if len(both) else np.nan,
                "mean_abs_diff_ugm3": round(diff.abs().mean(), 2) if len(both) else np.nan,
                "pct_days_abs_diff_gt_10pct": round(100 * (diff.abs() > 0.1 * both.airnow).mean(), 1) if len(both) else np.nan,
                "pearson_r": round(both.openaq.corr(both.airnow), 4) if len(both) > 2 else np.nan,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    base = build_openaq_grid()

    grids = {name: exclude_runs(base, n) for name, n in SCENARIOS.items()}
    daily = {name: scenario_daily(g) for name, g in grids.items()}

    runs = repeat_runs(base)
    runs.to_csv(OUT_DIR / "repeat_runs_all.csv", index=False)
    run_len_dist = runs.groupby(["year", pd.cut(runs.length_h, [1, 2, 3, 5, 6, 7, 24, 10_000],
                                                 labels=["2", "3", "4-5", "6", "7", "8-24", ">24"])],
                                observed=False).size().unstack(fill_value=0)
    run_len_dist.to_csv(OUT_DIR / "repeat_run_length_by_year.csv")
    long_runs = runs[runs.length_h >= 6]
    impacts = run_daily_impacts(long_runs, daily)
    impacts.to_csv(OUT_DIR / "long_run_daily_impacts.csv", index=False)

    # scenario summary
    scen_rows = []
    for name, g in grids.items():
        d = daily[name]
        changed = (d["pm25_daily_mean"] - daily["S0_unflagged"]["pm25_daily_mean"]).abs()
        scen_rows.append({
            "scenario": name,
            "hours_excluded_by_rule": int(g["excluded_by_run_rule"].sum()),
            "valid_hours": int(g["valid"].sum()),
            "complete_days": int(d["complete"].sum()),
            "days_lost_vs_S0": int((daily["S0_unflagged"]["complete"] & ~d["complete"]).sum()),
            "days_mean_changed_still_complete": int((changed > 0).sum()),
            "max_abs_daily_mean_change_ugm3": float(changed.max()) if changed.notna().any() else 0.0,
        })
    scen = pd.DataFrame(scen_rows)
    scen.to_csv(OUT_DIR / "scenario_summary.csv", index=False)

    # weekly
    weekly_year, weekly_season, err_tables = [], [], []
    for name, d in daily.items():
        wk = weekly_completeness(d)
        wk.to_csv(OUT_DIR / f"weekly_{name}.csv")
        weekly_year.append(weekly_threshold_counts(wk, "year").assign(scenario=name))
        weekly_season.append(weekly_threshold_counts(wk, "smog_season").assign(scenario=name))
        err_tables.append(missing_day_error(d, wk).assign(scenario=name))
    weekly_year = pd.concat(weekly_year)
    weekly_season = pd.concat(weekly_season)
    errs = pd.concat(err_tables)
    weekly_year.to_csv(OUT_DIR / "weekly_threshold_counts_by_year.csv")
    weekly_season.to_csv(OUT_DIR / "weekly_threshold_counts_by_smog_season.csv")
    errs.to_csv(OUT_DIR / "weekly_missing_day_error.csv")

    # AirNow comparison (original source)
    an_hourly, covered_windows = airnow_hourly_series()
    covered = covered_windows.index
    oq_valid = base["value_valid"].dropna()
    lags = lag_alignment(oq_valid, an_hourly)
    lags.to_csv(OUT_DIR / "airnow_lag_alignment.csv", index=False)
    lag_by_window = pd.concat(
        {w: lag_alignment(oq_valid[oq_valid.index.isin(idx)], an_hourly[an_hourly.index.isin(idx)]).set_index("lag_h")["pct_equal"]
         for w, idx in covered_windows.groupby(covered_windows).groups.items()}, axis=1).T
    lag_by_window.columns = [f"pct_equal_lag_{c:+d}h" for c in lag_by_window.columns]
    lag_by_window.to_csv(OUT_DIR / "airnow_lag_alignment_by_window.csv")
    hcmp, hsum = hourly_comparison(base, an_hourly, covered_windows)
    hcmp.to_csv(OUT_DIR / "airnow_hourly_comparison.csv")
    hsum.to_csv(OUT_DIR / "airnow_hourly_comparison_by_window.csv")

    # runs that fall inside fetched AirNow windows: did the original also repeat?
    run_rows = []
    for _, r in runs.iterrows():
        hrs = pd.date_range(r.first_hour_end, r.last_hour_end, freq="h")
        if not hrs.isin(covered).all():
            continue
        a = an_hourly.reindex(hrs)
        run_rows.append({**r[["first_hour_end", "last_hour_end", "length_h", "value"]].to_dict(),
                         "airnow_hours_present": int(a.notna().sum()),
                         "airnow_all_equal_run_value": bool(a.notna().all() and ((a - r.value).abs() <= MATCH_TOL).all()),
                         "airnow_values": ";".join("NA" if pd.isna(v) else f"{v:g}" for v in a)})
    runs_vs_airnow = pd.DataFrame(run_rows)
    runs_vs_airnow.to_csv(OUT_DIR / "repeat_runs_vs_airnow.csv", index=False)
    runs_vs_airnow_by_window = runs_vs_airnow.groupby(runs_vs_airnow["first_hour_end"].astype(str).str[:7]).agg(
        runs=("length_h", "size"),
        airnow_also_repeats=("airnow_all_equal_run_value", "sum"),
        airnow_absent=("airnow_hours_present", lambda x: int((x == 0).sum())),
    )
    runs_vs_airnow_by_window.index.name = "month"
    runs_vs_airnow_by_window.to_csv(OUT_DIR / "repeat_runs_vs_airnow_by_window.csv")

    an_daily = aa.daily(AIRNOW_AQSID, "2019-05-22", "2025-03-06")
    an_daily[["date", "value", "parameter", "units", "averaging_period", "archive_file"]].to_csv(
        PROJECT_ROOT / "data" / "processed" / "airnow_586PK3010003_daily.csv", index=False)
    dcmp = daily_comparison(daily, an_daily)
    dcmp.to_csv(OUT_DIR / "airnow_daily_comparison_by_year.csv", index=False)

    last_valid = base.index[base["valid"]].max()
    summary = {
        "openaq_last_row_timestamp": str(base.index.max()),
        "openaq_last_valid_timestamp": str(last_valid),
        "airnow_daily_last_date": str(an_daily["date"].max().date()),
        "airnow_daily_first_date": str(an_daily["date"].min().date()),
        "airnow_daily_days": len(an_daily),
        "repeat_runs_ge2": len(runs),
        "repeat_runs_ge6": int((runs.length_h >= 6).sum()),
        "repeat_runs_ge7": int((runs.length_h >= 7).sum()),
        "airnow_hourly_hours_covered": len(covered),
        "runs_fully_inside_airnow_windows": len(runs_vs_airnow),
    }
    (OUT_DIR / "stage1c_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print(json.dumps(summary, indent=2, default=str))
    for title, t in [("SCENARIOS", scen), ("RUN LENGTH BY YEAR", run_len_dist), ("LONG RUNS (>=6h)", long_runs),
                     ("LONG RUN DAILY IMPACTS", impacts), ("LAG ALIGNMENT", lags), ("LAG BY WINDOW", lag_by_window), ("HOURLY COMPARISON BY WINDOW", hsum),
                     ("RUNS VS AIRNOW (summary)", runs_vs_airnow.drop(columns="airnow_values") if len(runs_vs_airnow) else runs_vs_airnow),
                     ("DAILY COMPARISON", dcmp), ("WEEKLY BY YEAR", weekly_year), ("WEEKLY BY SEASON", weekly_season),
                     ("MISSING-DAY ERROR", errs)]:
        print(f"\n=== {title}\n{t.to_string()}")


if __name__ == "__main__":
    main()
