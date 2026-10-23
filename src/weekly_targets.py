"""Weekly mean PM2.5 targets built from daily means (no I/O, pure functions).

Conventions (see CLAUDE.md data rules and results/tables/forecasting_design.md):
- Units: µg/m³. Values are passed through unchanged; no unit conversion is done here.
- Dates: Lahore local calendar dates (PKT, UTC+05:00), tz-naive, one row per day. Any
  tz-aware or time-of-day component raises, because the day assignment must already have
  been done upstream (src/pm25_qc.py) on local time.
- Daily eligibility: a day is eligible only if it has >= MIN_VALID_HOURS (18 of 24) valid
  hours AND its daily mean is a finite, non-negative number. This is recomputed from the hour
  count; any upstream "complete" flag is ignored on purpose.
- Week boundary: Monday–Sunday on local dates (decided 2026-10-20; see CLAUDE.md).
  Monday–Sunday weeks coincide with ISO-8601 weeks.
- Missing data: never imputed. Calendar days absent from the input are counted as missing
  (the record is reindexed to the full calendar range, values are not filled). Invalid days
  are counted and excluded from the weekly mean.
- Weekly mean: the mean of the eligible daily means in the week. When a week has fewer than
  seven eligible days this is the mean of the observed days only, which is NOT necessarily
  the true seven-day mean; such weeks are flagged (complete_7_of_7 is False).
- The weekly completeness threshold (min_valid_days) must be passed explicitly (5, 6 or 7).
  The project uses 6 (decided 2026-10-20; passed by src.stage2_weekly).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_VALID_HOURS = 18  # per CLAUDE.md: >= 18 of 24 valid hourly observations
HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7
ALLOWED_MIN_VALID_DAYS = (5, 6, 7)
WEEK_START_DAY = "Monday"  # decided 2026-10-20

# Defaults match data/processed/openaq_8664_daily.csv
DEFAULT_DATE_COL = "date"
DEFAULT_MEAN_COL = "pm25_daily_mean"
DEFAULT_HOURS_COL = "hours_valid"

WEEKLY_COLUMNS = [
    "week_start",
    "week_end",
    "days_in_input",
    "absent_days_in_record",
    "days_outside_record",
    "ineligible_input_days",
    "eligible_days",
    "missing_or_invalid_days",
    "weekly_mean_observed_days",
    "min_valid_days",
    "eligible",
    "complete_7_of_7",
    "partial_week",
]


def _validate_min_valid_days(min_valid_days) -> int:
    ok = (
        isinstance(min_valid_days, (int, np.integer))
        and not isinstance(min_valid_days, (bool, np.bool_))
        and int(min_valid_days) in ALLOWED_MIN_VALID_DAYS
    )
    if not ok:
        raise ValueError(
            f"min_valid_days must be one of {ALLOWED_MIN_VALID_DAYS} (int); got {min_valid_days!r}"
        )
    return int(min_valid_days)


def _parse_dates(values: pd.Series, date_col: str) -> pd.Series:
    if values.isna().any():
        raise ValueError(f"{date_col!r} has {int(values.isna().sum())} missing date(s)")
    if isinstance(values.dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{date_col!r} must be tz-naive local (PKT) dates, got {values.dtype}")
    dates = pd.to_datetime(values, errors="coerce")
    bad = dates.isna()
    if bad.any():
        examples = values[bad].astype(str).head(5).tolist()
        raise ValueError(f"{date_col!r} has {int(bad.sum())} non-parseable date(s), e.g. {examples}")
    if isinstance(dates.dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{date_col!r} must be tz-naive local (PKT) dates, got tz-aware values")
    has_time = dates != dates.dt.normalize()
    if has_time.any():
        examples = values[has_time].astype(str).head(5).tolist()
        raise ValueError(f"{date_col!r} must be calendar dates without a time of day, e.g. {examples}")
    return dates


def daily_eligibility(
    daily: pd.DataFrame,
    *,
    date_col: str = DEFAULT_DATE_COL,
    mean_col: str = DEFAULT_MEAN_COL,
    hours_col: str = DEFAULT_HOURS_COL,
) -> pd.DataFrame:
    """Validate a daily table and flag each day's eligibility for weekly aggregation.

    Raises ValueError on: missing columns, missing or non-parseable dates, tz-aware dates,
    dates with a time of day, duplicate dates (listed in the message), and hour counts that
    are missing, non-numeric, non-integer, or outside 0–24.

    Daily means that are NaN, non-numeric, infinite or negative are NOT errors: the day is
    marked invalid (``valid_mean`` False), counted, and never imputed.

    Returns a new frame sorted by date with columns: date, hours_valid, daily_mean
    (numeric, µg/m³; invalid entries become NaN), meets_hours, valid_mean, eligible, reason.
    """
    missing = [c for c in (date_col, mean_col, hours_col) if c not in daily.columns]
    if missing:
        raise ValueError(f"daily input is missing column(s): {missing}")

    dates = _parse_dates(daily[date_col], date_col)
    dup = dates.duplicated(keep=False)
    if dup.any():
        dup_dates = sorted(dates[dup].dt.strftime("%Y-%m-%d").unique().tolist())
        raise ValueError(f"duplicate dates in {date_col!r}: {dup_dates}")

    hours = pd.to_numeric(daily[hours_col], errors="coerce")
    bad_hours = hours.isna() | (hours < 0) | (hours > HOURS_PER_DAY) | (hours != np.floor(hours))
    if bad_hours.any():
        examples = daily.loc[bad_hours, [date_col, hours_col]].head(5).to_dict("records")
        raise ValueError(
            f"{hours_col!r} must be integers in 0–{HOURS_PER_DAY}; {int(bad_hours.sum())} bad row(s), e.g. {examples}"
        )

    means = pd.to_numeric(daily[mean_col], errors="coerce").astype(float)
    valid_mean = means.notna() & np.isfinite(means) & (means >= 0)
    meets_hours = hours >= MIN_VALID_HOURS
    eligible = meets_hours & valid_mean

    reason = np.select(
        [eligible, ~meets_hours & ~valid_mean, ~meets_hours],
        ["ok", "insufficient_hours_and_invalid_mean", "insufficient_hours"],
        default="invalid_mean",
    )
    out = pd.DataFrame(
        {
            "date": dates.to_numpy(),
            "hours_valid": hours.astype(int).to_numpy(),
            "daily_mean": means.where(valid_mean).to_numpy(),
            "meets_hours": meets_hours.to_numpy(),
            "valid_mean": valid_mean.to_numpy(),
            "eligible": eligible.to_numpy(),
            "reason": reason,
        }
    )
    return out.sort_values("date", ignore_index=True)


def summarize_daily_validity(days: pd.DataFrame) -> dict:
    """Counts of days by eligibility reason, from the output of ``daily_eligibility``."""
    counts = days["reason"].value_counts()
    return {
        "days_in_input": int(len(days)),
        "eligible_days": int(days["eligible"].sum()),
        "invalid_mean_days": int((~days["valid_mean"]).sum()),
        "insufficient_hours_days": int((~days["meets_hours"]).sum()),
        "by_reason": {str(k): int(v) for k, v in counts.items()},
    }


def week_start_of(dates: pd.Series) -> pd.Series:
    """Monday (00:00, local date) of the Monday–Sunday week containing each date."""
    return dates - pd.to_timedelta(dates.dt.dayofweek, unit="D")


def build_weekly_targets(
    daily: pd.DataFrame,
    *,
    min_valid_days: int,
    date_col: str = DEFAULT_DATE_COL,
    mean_col: str = DEFAULT_MEAN_COL,
    hours_col: str = DEFAULT_HOURS_COL,
) -> pd.DataFrame:
    """Aggregate daily PM2.5 means into Monday–Sunday weekly targets.

    ``min_valid_days`` is required (no default) and must be 5, 6 or 7; the project has not
    yet chosen a weekly completeness threshold.

    The record spans the first to the last date in the input. Every calendar day of every
    week that touches that span is represented; days absent from the input are missing and
    are never filled. Weeks that extend before the first or after the last input date are
    ``partial_week``; their out-of-record days count as missing.

    Output: one row per week (sorted), with columns
        week_start, week_end          Monday and Sunday (local dates)
        days_in_input                 calendar days of the week present as input rows
        absent_days_in_record         days inside the record span with no input row
        days_outside_record           days before the first / after the last input date
        ineligible_input_days         input rows failing the 18-hour or valid-mean rule
        eligible_days                 days counted in the weekly mean (0–7)
        missing_or_invalid_days       7 − eligible_days
        weekly_mean_observed_days     mean of eligible daily means (µg/m³); NaN if none.
                                      With fewer than 7 eligible days this is the mean of
                                      the observed days only, NOT necessarily the true
                                      seven-day mean.
        min_valid_days                threshold used
        eligible                      eligible_days >= min_valid_days
        complete_7_of_7               eligible_days == 7 (False flags subset-based means)
        partial_week                  week cut off by the start/end of the record
    """
    min_valid_days = _validate_min_valid_days(min_valid_days)
    days = daily_eligibility(daily, date_col=date_col, mean_col=mean_col, hours_col=hours_col)
    if days.empty:
        raise ValueError("daily input has no rows")

    first, last = days["date"].iloc[0], days["date"].iloc[-1]
    calendar = pd.date_range(
        first - pd.Timedelta(days=first.dayofweek),
        last + pd.Timedelta(days=6 - last.dayofweek),
        freq="D",
    )
    full = days.set_index("date").reindex(calendar)  # no fill: absent days stay NaN
    in_input = full["hours_valid"].notna()
    in_record = (calendar >= first) & (calendar <= last)
    eligible_day = full["eligible"].eq(True)  # absent days (NaN) -> False

    frame = pd.DataFrame(
        {
            "week_start": week_start_of(pd.Series(calendar)).to_numpy(),
            "in_input": in_input.to_numpy(),
            "absent_in_record": (in_record & ~in_input).to_numpy(),
            "outside_record": ~in_record,
            "ineligible_input": (in_input & ~eligible_day).to_numpy(),
            "eligible_day": eligible_day.to_numpy(),
            "eligible_mean": full["daily_mean"].where(eligible_day).to_numpy(),
        }
    )
    weekly = frame.groupby("week_start", sort=True).agg(
        days_in_input=("in_input", "sum"),
        absent_days_in_record=("absent_in_record", "sum"),
        days_outside_record=("outside_record", "sum"),
        ineligible_input_days=("ineligible_input", "sum"),
        eligible_days=("eligible_day", "sum"),
        weekly_mean_observed_days=("eligible_mean", "mean"),
    )
    weekly = weekly.reset_index()
    count_cols = [
        "days_in_input",
        "absent_days_in_record",
        "days_outside_record",
        "ineligible_input_days",
        "eligible_days",
    ]
    weekly[count_cols] = weekly[count_cols].astype(int)
    weekly["week_end"] = weekly["week_start"] + pd.Timedelta(days=DAYS_PER_WEEK - 1)
    weekly["missing_or_invalid_days"] = DAYS_PER_WEEK - weekly["eligible_days"]
    weekly["min_valid_days"] = min_valid_days
    weekly["eligible"] = weekly["eligible_days"] >= min_valid_days
    weekly["complete_7_of_7"] = weekly["eligible_days"] == DAYS_PER_WEEK
    weekly["partial_week"] = weekly["days_outside_record"] > 0
    return weekly[WEEKLY_COLUMNS]
