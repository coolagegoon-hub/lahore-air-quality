"""Reference (non-ML) baselines for weekly mean PM2.5 forecasts.

Forecast setup (see results/tables/forecasting_design.md):
- Target: weekly mean PM2.5 (µg/m³) of week T, Monday–Sunday on Lahore local dates (PKT,
  UTC+05:00). Monday–Sunday boundary decided 2026-10-20 (CLAUDE.md).
- Issuance cutoff: Monday 00:00 local time at the start of week T. Only weeks that ended
  before the cutoff (week_end < cutoff, i.e. week_start <= T − 7 days) may be used. Every
  function filters to that set itself, so passing a frame that contains the target week or
  later weeks cannot change a prediction.
- Only weeks flagged ``eligible`` (by src.weekly_targets.build_weekly_targets with an
  explicitly chosen min_valid_days) are ever used as predictors.

Input ``weekly`` frame: columns week_start (Monday), week_end (Sunday),
weekly_mean_observed_days (µg/m³) and eligible (bool), one row per week.

Each baseline returns a dict with ``prediction`` (float, NaN when unavailable) and
``reason`` ("ok" or why no prediction was made). No randomness is involved.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

DAYS_PER_WEEK = 7
MAX_WINDOW_WEEKS = 25  # keeps seasonal windows of consecutive years from overlapping
REQUIRED_WEEKLY_COLUMNS = ("week_start", "week_end", "weekly_mean_observed_days", "eligible")


def issuance_cutoff(target_week_start) -> pd.Timestamp:
    """Cutoff for forecasting week T: Monday 00:00 local at the start of T (tz-naive)."""
    ts = pd.Timestamp(target_week_start)
    if ts.tzinfo is not None:
        raise ValueError("target_week_start must be a tz-naive local (PKT) date")
    if ts != ts.normalize() or ts.dayofweek != 0:
        raise ValueError(f"target_week_start must be a Monday at 00:00, got {ts}")
    return ts


def _validate_weekly(weekly: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_WEEKLY_COLUMNS if c not in weekly.columns]
    if missing:
        raise ValueError(f"weekly frame is missing column(s): {missing}")
    w = weekly.loc[:, list(REQUIRED_WEEKLY_COLUMNS)].copy()
    w["week_start"] = pd.to_datetime(w["week_start"])
    w["week_end"] = pd.to_datetime(w["week_end"])
    if w["week_start"].duplicated().any():
        raise ValueError("weekly frame has duplicate week_start values")
    if (w["week_start"].dt.dayofweek != 0).any():
        raise ValueError("week_start values must all be Mondays")
    if (w["week_end"] - w["week_start"] != pd.Timedelta(days=DAYS_PER_WEEK - 1)).any():
        raise ValueError("week_end must equal week_start + 6 days")
    if w["eligible"].dtype != bool:
        raise ValueError("eligible column must be boolean")
    return w.sort_values("week_start", ignore_index=True)


def available_before_cutoff(weekly: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Eligible weeks that ended strictly before ``cutoff`` (the only usable predictors)."""
    w = _validate_weekly(weekly)
    usable = (w["week_end"] < cutoff) & w["eligible"] & w["weekly_mean_observed_days"].notna()
    return w.loc[usable].reset_index(drop=True)


def persistence(
    weekly: pd.DataFrame,
    target_week_start,
    *,
    max_age_weeks: int | None = None,
) -> dict:
    """Predict week T as the weekly mean of the most recent ELIGIBLE week before the cutoff.

    Ineligible weeks are skipped, never used. ``age_weeks`` is the gap in weeks between the
    source week and T (1 = the immediately preceding week). ``max_age_weeks`` (optional,
    default None = no limit) rejects a source week older than that many weeks; the result is
    then NaN with reason "source_too_old".
    """
    cutoff = issuance_cutoff(target_week_start)
    if max_age_weeks is not None and (isinstance(max_age_weeks, bool) or int(max_age_weeks) < 1):
        raise ValueError("max_age_weeks must be a positive integer or None")
    out = {
        "target_week_start": cutoff,
        "cutoff": cutoff,
        "prediction": np.nan,
        "source_week_start": pd.NaT,
        "age_weeks": np.nan,
        "reason": "no_eligible_prior_week",
    }
    avail = available_before_cutoff(weekly, cutoff)
    if avail.empty:
        return out
    src = avail.iloc[-1]
    age = int((cutoff - src["week_start"]).days // DAYS_PER_WEEK)
    out.update(source_week_start=src["week_start"], age_weeks=age)
    if max_age_weeks is not None and age > max_age_weeks:
        out["reason"] = "source_too_old"
        return out
    out.update(prediction=float(src["weekly_mean_observed_days"]), reason="ok")
    return out


def seasonal_climatology(
    weekly: pd.DataFrame,
    target_week_start,
    *,
    window_weeks: int,
    min_years: int,
    min_samples: int,
) -> dict:
    """Median of eligible weekly means at the same seasonal position in PRIOR years only.

    Seasonal position: for each prior year k = 1, 2, ..., the anniversary date
    A_k = T − k calendar years (pandas DateOffset; 29 Feb maps to 28 Feb). A source week
    belongs to year k's window if its week_start lies within ±(7·window_weeks + 3) days of
    A_k. Because week starts are Mondays, each window holds exactly 2·window_weeks + 1
    candidate weeks: the week nearest the anniversary and ``window_weeks`` either side. This
    avoids ISO week-53 ambiguity and wraps across New Year naturally (e.g. T in early January
    draws on late-December weeks of earlier years). The current year (k = 0) is never used,
    nor is the target week or anything after the cutoff; all source weeks must also have
    ended before the cutoff.

    Requires at least ``min_samples`` eligible source weeks from at least ``min_years``
    distinct prior years; otherwise returns NaN with a reason.
    """
    cutoff = issuance_cutoff(target_week_start)
    for name, val, lo in (("window_weeks", window_weeks, 0), ("min_years", min_years, 1), ("min_samples", min_samples, 1)):
        if isinstance(val, bool) or not isinstance(val, (int, np.integer)) or val < lo:
            raise ValueError(f"{name} must be an integer >= {lo}, got {val!r}")
    if window_weeks > MAX_WINDOW_WEEKS:
        raise ValueError(f"window_weeks must be <= {MAX_WINDOW_WEEKS}")

    out = {
        "target_week_start": cutoff,
        "cutoff": cutoff,
        "prediction": np.nan,
        "n_samples": 0,
        "n_years": 0,
        "source_week_starts": [],
        "reason": "insufficient_history",
    }
    avail = available_before_cutoff(weekly, cutoff)
    if avail.empty:
        return out

    half_width = pd.Timedelta(days=DAYS_PER_WEEK * window_weeks + 3)
    max_k = cutoff.year - avail["week_start"].min().year + 1
    ks = np.arange(1, max_k + 1)
    anniversaries = pd.DatetimeIndex([cutoff - pd.DateOffset(years=int(k)) for k in ks])
    # (n_weeks, n_years) distance matrix; windows never overlap because window_weeks <= 25.
    starts = avail["week_start"].to_numpy()[:, None]
    in_window = np.abs(starts - anniversaries.to_numpy()[None, :]) <= half_width.to_timedelta64()
    matched = in_window.any(axis=1)
    sources = avail.loc[matched]
    years_used = int(in_window.any(axis=0).sum())

    out.update(
        n_samples=int(len(sources)),
        n_years=years_used,
        source_week_starts=sources["week_start"].tolist(),
    )
    if len(sources) < min_samples:
        out["reason"] = "too_few_samples"
        return out
    if years_used < min_years:
        out["reason"] = "too_few_years"
        return out
    out.update(prediction=float(sources["weekly_mean_observed_days"].median()), reason="ok")
    return out


def predict_baselines(
    weekly: pd.DataFrame,
    target_week_starts: Iterable,
    *,
    persistence_kwargs: dict | None = None,
    climatology_kwargs: dict,
) -> pd.DataFrame:
    """Run both baselines for each target week, strictly chronologically.

    For every target T the frame is first truncated to weeks that ended before T's cutoff,
    then each baseline is called on that truncated frame (the baselines also filter
    internally). ``climatology_kwargs`` must give window_weeks, min_years and min_samples.

    The returned ``observed`` / ``observed_eligible`` columns are the target week's own value
    and flag, attached AFTER prediction for later scoring only; they are never inputs.
    """
    persistence_kwargs = persistence_kwargs or {}
    w = _validate_weekly(weekly)
    targets = sorted({issuance_cutoff(t) for t in target_week_starts})
    rows = []
    for t in targets:
        past = w.loc[w["week_end"] < t]
        p = persistence(past, t, **persistence_kwargs)
        c = seasonal_climatology(past, t, **climatology_kwargs)
        rows.append(
            {
                "target_week_start": t,
                "cutoff": t,
                "persistence": p["prediction"],
                "persistence_source_week_start": p["source_week_start"],
                "persistence_age_weeks": p["age_weeks"],
                "persistence_reason": p["reason"],
                "climatology": c["prediction"],
                "climatology_n_samples": c["n_samples"],
                "climatology_n_years": c["n_years"],
                "climatology_reason": c["reason"],
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    truth = w.set_index("week_start")[["weekly_mean_observed_days", "eligible"]]
    truth = truth.rename(columns={"weekly_mean_observed_days": "observed", "eligible": "observed_eligible"})
    return out.join(truth, on="target_week_start")
