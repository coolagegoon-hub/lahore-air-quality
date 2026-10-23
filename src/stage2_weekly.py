"""Stage 2: final daily and weekly PM2.5 target series, and reference-baseline scores.

Decisions applied (CLAUDE.md, decided 2026-10-18 / 2026-10-20):
- Primary series: AirNow rebuild, AQS 586PK3010003 (src.airnow_hourly_series), negatives invalid,
  read from its saved hourly file data/processed/airnow_586PK3010003_hourly.csv.
- Repeated values: every hour of a run of >= RUN_RULE_HOURS (7) consecutive identical valid
  values is invalid (src.stage1c_analysis.exclude_runs), applied before the daily rule.
- Daily: >= 18 of 24 valid hours (src.pm25_qc).
- Weekly: Monday–Sunday PKT, eligible when >= MIN_VALID_DAYS (6) of 7 days are valid
  (src.weekly_targets). A 6-day mean is not necessarily the true 7-day mean.

Baselines (src.baselines) need no fitting: every prediction uses only eligible weeks that ended
before the target week's Monday 00:00 cutoff, so scoring them week by week is a strict
chronological walk-forward evaluation. Climatology parameters are fixed in advance
(CLIMATOLOGY_KWARGS) and were not tuned on these data.

AirNow data are preliminary (U.S. Department of State / EPA AirNow program).

Usage:
    python -m src.stage2_weekly
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import airnow_hourly_series as ahs
from src import baselines as bl
from src import pm25_qc as qc
from src import stage1c_analysis as s1c
from src import weekly_targets as wt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage2"
RUN_RULE_HOURS = 7
MIN_VALID_DAYS = 6
CLIMATOLOGY_KWARGS = {"window_weeks": 2, "min_years": 2, "min_samples": 4}  # provisional, not tuned
SMOG_MONTHS = (10, 11, 12, 1)


def final_daily(grid: pd.DataFrame, run_rule_hours: int = RUN_RULE_HOURS) -> tuple[pd.DataFrame, int]:
    """Apply the run rule to the hourly grid, then the 18/24 daily rule. Returns (daily, hours excluded)."""
    g = s1c.exclude_runs(grid, run_rule_hours)
    return qc.daily_summary(g), int(g["excluded_by_run_rule"].sum())


def weekly_from_daily(daily: pd.DataFrame, min_valid_days: int = MIN_VALID_DAYS) -> pd.DataFrame:
    w = wt.build_weekly_targets(daily.reset_index()[["date", "hours_valid", "pm25_daily_mean"]],
                                min_valid_days=min_valid_days)
    thursday = w["week_start"] + pd.Timedelta(days=3)
    w["smog_season_week"] = thursday.dt.month.isin(SMOG_MONTHS)
    return w


def score(obs: pd.Series, pred: pd.Series) -> dict:
    """Error metrics on pairs where both are present (pred − obs). No pairs -> NaNs."""
    m = obs.notna() & pred.notna()
    e = (pred[m] - obs[m]).to_numpy(dtype=float)
    if len(e) == 0:
        return {"n": 0, "mae": np.nan, "rmse": np.nan, "bias": np.nan, "median_ae": np.nan}
    return {"n": int(len(e)), "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))),
            "bias": float(np.mean(e)), "median_ae": float(np.median(np.abs(e)))}


def score_table(preds: pd.DataFrame) -> pd.DataFrame:
    """Scores on several clearly defined target sets (all restricted to eligible observed weeks)."""
    p = preds[preds["observed_eligible"].eq(True)]
    both = p["persistence"].notna() & p["climatology"].notna()
    sets = {
        "persistence_any_age": (p.index, "persistence"),
        "persistence_age_1": (p.index[p["persistence_age_weeks"].eq(1)], "persistence"),
        "climatology_available": (p.index, "climatology"),
        "common_persistence": (p.index[both], "persistence"),
        "common_climatology": (p.index[both], "climatology"),
        "common_smog_persistence": (p.index[both & p["smog_season_week"]], "persistence"),
        "common_smog_climatology": (p.index[both & p["smog_season_week"]], "climatology"),
        "common_nonsmog_persistence": (p.index[both & ~p["smog_season_week"]], "persistence"),
        "common_nonsmog_climatology": (p.index[both & ~p["smog_season_week"]], "climatology"),
    }
    rows = []
    for name, (idx, col) in sets.items():
        rows.append({"set": name, "baseline": col, **score(p.loc[idx, "observed"], p.loc[idx, col])})
    return pd.DataFrame(rows).set_index("set").round(2)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)

    grid = ahs.load_saved_grid()  # saved by src.airnow_hourly_series (negatives invalid); no archive download
    daily, excluded = final_daily(grid)
    weekly = weekly_from_daily(daily)

    daily.to_csv(PROJECT_ROOT / "data" / "processed" / "pm25_daily_final.csv")
    weekly.to_csv(PROJECT_ROOT / "data" / "processed" / "pm25_weekly_target.csv", index=False)

    full = weekly[~weekly["partial_week"]]
    targets = full["week_start"].tolist()
    preds = bl.predict_baselines(weekly, targets, climatology_kwargs=CLIMATOLOGY_KWARGS)
    preds = preds.merge(weekly[["week_start", "smog_season_week", "eligible_days"]],
                        left_on="target_week_start", right_on="week_start", how="left").drop(columns="week_start")
    preds.to_csv(OUT_DIR / "baseline_predictions.csv", index=False)
    scores = score_table(preds)
    scores.to_csv(OUT_DIR / "baseline_scores.csv")

    years = full.assign(year=(full["week_start"] + pd.Timedelta(days=3)).dt.year)
    per_year = years.groupby("year").agg(full_weeks=("eligible", "size"), eligible_weeks=("eligible", "sum"),
                                          weeks_7_of_7=("complete_7_of_7", "sum"))
    per_year.to_csv(OUT_DIR / "weekly_eligibility_by_year.csv")
    elig = full[full["eligible"]]
    summary = {
        "source": "AirNow rebuild AQS 586PK3010003 (preliminary data)",
        "negative_policy": "invalid",
        "run_rule_hours": RUN_RULE_HOURS, "hours_excluded_by_run_rule": excluded,
        "min_valid_days": MIN_VALID_DAYS,
        "daily_days": len(daily), "daily_complete": int(daily["complete"].sum()),
        "weeks_total": len(weekly), "weeks_partial": int(weekly["partial_week"].sum()),
        "full_weeks": len(full), "eligible_weeks": int(full["eligible"].sum()),
        "eligible_weeks_7_of_7": int(elig["complete_7_of_7"].sum()),
        "eligible_weeks_6_of_7": int((~elig["complete_7_of_7"]).sum()),
        "eligible_smog_weeks": int(elig["smog_season_week"].sum()),
        "eligible_weekly_mean_min_max": [round(float(elig.weekly_mean_observed_days.min()), 1),
                                         round(float(elig.weekly_mean_observed_days.max()), 1)],
        "first_eligible_week": str(elig["week_start"].min().date()), "last_eligible_week": str(elig["week_start"].max().date()),
        "climatology_kwargs": CLIMATOLOGY_KWARGS,
        "persistence_reasons": preds["persistence_reason"].value_counts().to_dict(),
        "climatology_reasons": preds["climatology_reason"].value_counts().to_dict(),
        "persistence_age_weeks_on_eligible_targets": preds.loc[preds.observed_eligible.eq(True), "persistence_age_weeks"].value_counts().sort_index().to_dict(),
    }
    (OUT_DIR / "stage2_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print("\n=== WEEKLY ELIGIBILITY BY YEAR\n", per_year.to_string())
    print("\n=== BASELINE SCORES (µg/m³; error = prediction − observed)\n", scores.to_string())


if __name__ == "__main__":
    main()
