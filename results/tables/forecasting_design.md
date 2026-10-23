# Forecasting Design — Weekly PM2.5 Targets and Baselines (DRAFT, awaiting review)

> **Status update (2026-10-23):** Decided: Monday–Sunday PKT weeks and the ≥ 6/7 threshold (2026-10-20), with the AirNow rebuild as primary series. §5.3 is now implemented: the PM2.5-history model (`src/history_model.py`) and walk-forward scoring (`src/stage2_weekly.py`, `src/main_model.py`). Data latency remains a documented assumption (zero embargo); embargo options are still open.

Status: design and code only. **No real data has been processed with this code, and no forecast results exist.** The tests in `tests/test_weekly_targets.py` and `tests/test_baselines.py` use synthetic data only; they check that the code behaves as specified, not anything about Lahore air quality.

Code: `src/weekly_targets.py` (weekly target builder), `src/baselines.py` (persistence and seasonal climatology).

---

## 1. Data contract

### Daily input (to `build_weekly_targets`)
One row per Lahore local calendar date. Default column names match `data/processed/openaq_8664_daily.csv`; all are configurable.

| Column (default) | Meaning | Units / type |
|---|---|---|
| `date` | Local calendar date, **PKT (Asia/Karachi, UTC+05:00, no DST)**, tz-naive, no time of day | date |
| `pm25_daily_mean` | Daily mean PM2.5 of the valid hours | µg/m³ |
| `hours_valid` | Number of valid hourly observations that day | integer 0–24 |

Other columns (e.g. `complete`, `mean_all_valid_hours`) are ignored. In particular, an upstream `complete` flag is **not** trusted; eligibility is recomputed from `hours_valid`.

Hour-to-day assignment (hour-ending vs hour-beginning) is done upstream, before this stage. See `stage1c_data_quality_decisions.md` §1.

**Validation (raises an error):**
- missing, non-parseable, tz-aware or time-of-day dates;
- duplicate dates (the duplicates are listed);
- hour counts that are missing, non-numeric, non-integer or outside 0–24.

**Invalid days (counted, not errors):** a daily mean that is NaN, non-numeric, infinite or negative.

### Daily eligibility
A day is eligible only if **`hours_valid` ≥ 18** (`MIN_VALID_HOURS = 18`, i.e. 75 % of 24, per CLAUDE.md) **and** its daily mean is a finite, non-negative number.

### Weekly output (one row per Monday–Sunday week)

| Column | Meaning |
|---|---|
| `week_start`, `week_end` | Monday and Sunday (local dates) |
| `days_in_input` | Calendar days of the week present as input rows |
| `absent_days_in_record` | Days inside the record span with no input row |
| `days_outside_record` | Days before the first or after the last input date |
| `ineligible_input_days` | Input rows failing the 18-hour rule or the valid-mean rule |
| `eligible_days` | Days used in the weekly mean (0–7) |
| `missing_or_invalid_days` | 7 − `eligible_days` |
| `weekly_mean_observed_days` | Mean of the eligible daily means, in µg/m³. NaN if there are none. |
| `min_valid_days` | The threshold used (5, 6 or 7) |
| `eligible` | `eligible_days` ≥ `min_valid_days` |
| `complete_7_of_7` | `eligible_days` == 7 |
| `partial_week` | The week is cut off by the start or end of the record |

**Caution:** when `eligible_days` < 7, `weekly_mean_observed_days` is the mean of only the observed days. It is **not** necessarily the true seven-day mean. Such weeks have `complete_7_of_7 = False`.

## 2. Week boundary — PROVISIONAL

Weeks run **Monday 00:00 to Sunday 24:00, Lahore local time (PKT)**. This matches ISO-8601 weeks and the Stage 1C completeness tables.

**This is an assumption awaiting review, not a final decision.** Changing it means changing `week_start_of` in `src/weekly_targets.py` and the cutoff definition in `src/baselines.py`.

## 3. Missing-data handling

- **No imputation, anywhere.** No values are interpolated, filled or carried forward.
- **Missing calendar days:** the record is reindexed to every calendar day of every week from the first to the last input date. A date with no input row counts as missing (`absent_days_in_record`). Its value stays empty.
- **Invalid days:** these are input rows with fewer than 18 valid hours or an invalid mean. They are counted (`ineligible_input_days`; `summarize_daily_validity` gives counts by reason) and left out of the weekly mean.
- **Partial weeks:** these are the first and last weeks of the record when the record does not start on a Monday or end on a Sunday. Days outside the record count as missing.
  - A partial week is marked `partial_week = True` but can still be `eligible` if enough in-record days are eligible.
  - Whether partial weeks should be dropped outright is an open decision (§7).
- **Weekly mean:** this is the unweighted mean of the eligible daily means. A week with no eligible days gets NaN.

## 4. Forecast timing and cutoff

- **Target:** `weekly_mean_observed_days` of week T, for weeks with `eligible = True` under the chosen threshold.
- **Issuance cutoff:** Monday 00:00 PKT at the start of week T.
- **Usable information:** only weeks that ended before the cutoff (`week_end < cutoff`, i.e. `week_start ≤ T − 7 days`), and among those, only `eligible` weeks.
- **How this is enforced:**
  - Every baseline filters to that set internally.
  - `predict_baselines` also truncates the frame per target before calling them.
  - The target's own value (`observed`) is joined only after prediction, for scoring.
- **Not yet considered:** real-time data latency, i.e. whether the previous Sunday's data is actually available by Monday 00:00. The retrospective archive may arrive later than real time. If a lag is needed, it would be an extra embargo parameter (§7).

## 5. Baselines

Both baselines are deterministic, use no randomness, and fit nothing. They therefore cannot leak information through fitted preprocessing.

### 5.1 Persistence — `persistence(weekly, T, max_age_weeks=None)`

- **Prediction:** the weekly mean of the most recent **eligible** week that ended before the cutoff.
- **Ineligible weeks:** skipped, never used.
- **Also returned:** `source_week_start` and `age_weeks` (1 means the week immediately before T).
- **No prediction (NaN):**
  - if no eligible prior week exists (`reason = "no_eligible_prior_week"`);
  - if `max_age_weeks` is set and the source week is older than that (`"source_too_old"`).
- **`max_age_weeks`:** optional; the default `None` means no limit. Its value is an open decision.

### 5.2 Seasonal climatology — `seasonal_climatology(weekly, T, *, window_weeks, min_years, min_samples)`

- **Seasonal position:**
  - For each prior year k = 1, 2, …, the anniversary is A_k = T − k calendar years. A 29 February maps to 28 February.
  - A source week belongs to year k's window if its `week_start` is within ±(7 × `window_weeks` + 3) days of A_k.
  - Because week starts are Mondays, each window contains exactly 2 × `window_weeks` + 1 weeks: the week nearest the anniversary plus `window_weeks` on each side.
- **Why this definition:**
  - It avoids ambiguity around ISO week 53.
  - It wraps across New Year naturally. For example, a target in the first week of January draws on late-December weeks of earlier years.
  - `window_weeks` ≤ 25, so windows from consecutive years never overlap.
- **Prediction:** the median of the eligible weekly means in all prior-year windows.
- **What is never used:**
  - the current year's weeks (k = 0);
  - the target week;
  - any week ending on or after the cutoff.
- **Required parameters (no defaults):** `window_weeks` ≥ 0, `min_years` ≥ 1, `min_samples` ≥ 1.
- **No prediction (NaN):**
  - if fewer than `min_samples` source weeks are available (`"too_few_samples"`);
  - if fewer than `min_years` distinct prior years contribute (`"too_few_years"`).
- **Record start:** windows truncated by the start of the record are used as far as they go. The count of contributing years includes them.

### 5.3 Not yet implemented
- **PM2.5-history-only model:** required by CLAUDE.md as a third reference. It is not written yet, because it involves fitting and must be fitted inside walk-forward folds.
- **Scoring metrics and walk-forward evaluation driver:** not written yet.

## 6. Weekly completeness alternatives

> **DECIDED 2026-10-20:** ≥ 6 of 7 valid days (one missing day allowed). The repeated-value rule is runs of ≥ 7 h invalid. The primary series is the AirNow rebuild. On the AirNow rebuild, ≥ 6/7 gives 236 of 299 full weeks (88 of 105 smog-season weeks); see `airnow_rebuild_report.md` §4. The OpenAQ table below is kept for the record.

**Provisional numbers (superseded).** These counts were computed previously in `stage1c_data_quality_decisions.md` §3 on **OpenAQ location 8664** data. They will change after the AirNow rebuild.

| Threshold | Weeks qualifying (of 301 full weeks) | Smog-season weeks, Oct–Jan (of 105) |
|---|---|---|
| 7/7 | 145 | 66 |
| ≥ 6/7 | 178 | 75 |
| ≥ 5/7 | 200 | 79 |

**Missing-day error experiment** (same source). For each 7/7 week, every possible 1-day and 2-day subset of days was removed:

| Days removed | Median absolute % error | 95th percentile % error |
|---|---|---|
| 1 day | about 3 % | about 10 % |
| 2 days | about 4–5 % | about 16 % |

This experiment assumes days go missing at random. If outages cluster in extreme conditions, the real error may be larger; this has not been tested.

**Trade-off:** a stricter threshold gives exact weekly means but fewer weeks, including very few in some smog seasons (2022-23 has 0 weeks at 7/7). A looser threshold keeps more weeks but adds error to the target.

The code supports all three thresholds; `min_valid_days` has no default, so it must be set explicitly.

## 7. Unresolved decisions

1. **Weekly completeness threshold:** 7/7, ≥ 6/7 or ≥ 5/7 (§6). Alternatively, use a coverage weight, or keep `eligible_days` as a quality flag or feature.
2. **Week boundary:** Monday–Sunday PKT is provisional (§2).
3. **Primary PM2.5 source:** the record is being rebuilt from the AirNow archive (US State Department monitor, AQS **586PK3010003**). The final daily input to `build_weekly_targets` will come from that rebuild, not from the OpenAQ 8664 file. All counts in §6 will need recomputing.
4. **Partial weeks** at the record edges: keep them if eligible, or always drop them.
5. **Persistence `max_age_weeks`:** whether to set a limit, and its value.
6. **Climatology parameters:** `window_weeks`, `min_years`, `min_samples`. Also whether to use the median (current choice) or the mean.
7. **Data latency and embargo:** whether a gap is needed between the last usable week and the cutoff, to reflect real-time data availability.
8. **AQI:** not computed. No AQI standard has been chosen (CLAUDE.md).
9. **Evaluation:** metrics, the walk-forward evaluation period, and the PM2.5-history-only baseline are still to be designed.
