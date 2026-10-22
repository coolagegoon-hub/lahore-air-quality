"""Hourly PM2.5 quality control and daily completeness for OpenAQ archive files.

Conventions (see CLAUDE.md data rules):
- Units: µg/m³ as reported by OpenAQ (checked; any other unit raises).
- Time zone: Asia/Karachi (PKT, UTC+05:00, no DST). Timestamps are kept tz-aware.
- Hour labelling: OpenAQ daily files hold timestamps 01:00 ... 00:00 (next day). We treat a
  timestamp as the END of its 1-hour averaging period, so 00:00 belongs to the previous day.
  This matches OpenAQ's own file grouping but is NOT verified against AirNow documentation.
  Change HOUR_LABEL_CONVENTION if it is later shown to be hour-beginning.
- Invalid hours: missing, non-numeric, or negative values (OpenAQ uses -999 as a fill value).
  No upper-bound filter is applied; very high values are counted and reported, not removed.
- Daily completeness: a daily mean is computed only when >= 18 of 24 hours are valid (75%).
- Repeated values: a valid hour whose value equals the immediately preceding valid hour
  (exactly one hour earlier). Reported as a diagnostic only; nothing is removed, because the
  source reports integer µg/m³ and genuine consecutive equal values are expected.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Asia/Karachi"
HOUR_LABEL_CONVENTION = "hour_ending"
MIN_VALID_HOURS = 18
HOURS_PER_DAY = 24
EXPECTED_UNITS = "µg/m³"
HIGH_VALUE_REVIEW_THRESHOLD = 1000.0  # µg/m³; reporting flag only, not a removal rule


def load_openaq_files(paths: list[Path]) -> pd.DataFrame:
    """Read OpenAQ archive daily files (both quoted and unquoted variants) into one frame."""
    frames = [pd.read_csv(p, compression="gzip", dtype=str).assign(source_file=p.name) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    return df


def parse_hourly(raw: pd.DataFrame, parameter: str = "pm25") -> pd.DataFrame:
    """Parse raw rows into tz-aware hourly records with a validity flag."""
    df = raw.loc[raw["parameter"] == parameter].copy()
    bad_units = set(df["units"].unique()) - {EXPECTED_UNITS}
    if bad_units:
        raise ValueError(f"unexpected units: {bad_units}")

    df["timestamp"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert(TZ)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["valid"] = df["value"].notna() & (df["value"] >= 0)
    return df[["timestamp", "value", "valid", "location_id", "sensors_id", "lat", "lon", "source_file"]]


def resolve_duplicate_timestamps(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Collapse rows sharing a timestamp. Identical values -> keep one; conflicting -> invalid."""
    dup_mask = df.duplicated("timestamp", keep=False)
    dups = df.loc[dup_mask]
    conflicting = dups.groupby("timestamp")["value"].nunique(dropna=False).gt(1)
    conflict_ts = conflicting[conflicting].index

    out = df.drop_duplicates("timestamp", keep="first").set_index("timestamp").sort_index()
    out.loc[out.index.isin(conflict_ts), "valid"] = False
    stats = {
        "rows_in": len(df),
        "duplicate_timestamp_rows": int(dup_mask.sum()),
        "duplicate_timestamps_identical": int((~conflicting).sum()),
        "duplicate_timestamps_conflicting": int(len(conflict_ts)),
        "rows_out": len(out),
    }
    return out, stats


def to_complete_hourly_grid(df: pd.DataFrame) -> pd.DataFrame:
    """Reindex to every hour between first and last timestamp so gaps are explicit rows."""
    grid = pd.date_range(df.index.min(), df.index.max(), freq="h", tz=TZ, name="timestamp")
    out = df[["value", "valid"]].reindex(grid)
    out["valid"] = out["valid"].fillna(False).astype(bool)
    out["present_in_source"] = df.index.to_series().reindex(grid).notna().to_numpy()
    out["value_valid"] = out["value"].where(out["valid"])
    return out


def assign_day(index: pd.DatetimeIndex, convention: str = HOUR_LABEL_CONVENTION) -> pd.DatetimeIndex:
    """Local calendar day each hourly record belongs to."""
    if convention == "hour_ending":
        start = index - pd.Timedelta(hours=1)
    elif convention == "hour_beginning":
        start = index
    else:
        raise ValueError(convention)
    return start.normalize().tz_localize(None)


def flag_repeats(hourly: pd.DataFrame) -> pd.DataFrame:
    """Flag valid hours equal to the valid hour exactly one hour earlier; label run lengths."""
    v = hourly["value_valid"]
    prev = v.shift(1)  # grid is complete and hourly, so shift(1) is exactly 1 h earlier
    repeat = v.notna() & prev.notna() & (v == prev)
    run_id = (~repeat).cumsum()
    run_len = repeat.groupby(run_id).transform("sum") + 1  # hours in the run of equal values
    out = hourly.copy()
    out["repeat_prev"] = repeat
    out["repeat_run_length"] = np.where(v.notna(), run_len, 0)
    return out


def daily_summary(hourly: pd.DataFrame, min_valid: int = MIN_VALID_HOURS) -> pd.DataFrame:
    """Daily valid-hour counts and the completeness-gated daily mean."""
    day = assign_day(hourly.index)
    g = hourly.groupby(day)
    daily = pd.DataFrame(
        {
            "hours_in_grid": g["valid"].size(),
            "hours_present": g["present_in_source"].sum(),
            "hours_valid": g["valid"].sum(),
            "mean_all_valid_hours": g["value_valid"].mean(),
            "repeat_hours": g["repeat_prev"].sum() if "repeat_prev" in hourly else np.nan,
        }
    )
    daily.index.name = "date"
    daily["complete"] = daily["hours_valid"] >= min_valid
    daily["pm25_daily_mean"] = daily["mean_all_valid_hours"].where(daily["complete"])
    return daily


def full_day_index(daily: pd.DataFrame) -> pd.DataFrame:
    """Add rows for calendar days with no hours at all (outside the hourly grid ends)."""
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D", name="date")
    out = daily.reindex(idx)
    fill = {"hours_in_grid": 0, "hours_present": 0, "hours_valid": 0, "repeat_hours": 0, "complete": False}
    return out.fillna(fill).astype({"complete": bool})
