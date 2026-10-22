# Stage 1B — OpenAQ Location 8664 (US Diplomatic Post: Lahore): Download, Coverage and Repeated-Value QC

- **Run date:** 2026-10-18
- **Code:** `src/download_openaq.py`, `src/pm25_qc.py`, `src/run_openaq_coverage.py`; tests in `tests/test_pm25_qc.py`
- **Reproduce:**
  ```bash
  .venv/bin/python -m src.download_openaq --location-id 8664
  .venv/bin/python -m src.run_openaq_coverage --location-id 8664
  .venv/bin/python -m pytest -q tests
  ```
- No model was built. All numbers below come from the downloaded files; nothing was imputed or invented.

## 1. Download

| Item | Value |
|---|---|
| Source | `https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=8664/` (anonymous) |
| Files listed / downloaded | 1,909 / 1,909 |
| Verification | All 1,909 matched the S3 listing in byte size and MD5 (= S3 ETag); SHA-256 recorded |
| Manifest | `results/tables/openaq_8664_download_manifest.csv` |
| Local copy | `data/raw/openaq/location_8664/year=YYYY/month=MM/…` (7.5 MB; git-ignored) |
| Downloaded at | 2026-10-18 08:40:53 UTC |

## 2. Data characteristics (verified from all files)

| Item | Value |
|---|---|
| Rows | 44,516 |
| Parameter | `pm25` only |
| Units | `µg/m³` only |
| Sensor ID | 25135 only |
| Coordinates | 31.560078 N, 74.33589 E (identical in every row) |
| Location name | `US Diplomatic Post: Lahore-8664` (30,648 rows); `Lahore-8664` (13,868 rows), i.e. the label changes over time |
| Timestamp range | 2019-05-23 03:00 to 2025-03-04 17:00 (+05:00) |
| Duplicate timestamps | 0 |
| Valid values range | 0 – 974 µg/m³ |
| Files containing no valid value (all `-999`) | 232 of 1,909 |

## 3. Processing rules applied

- **Invalid hour:** missing row, non-numeric value, or value < 0 (covers the `-999` fill value). There is **no upper-bound filter**. No valid value exceeds 1,000 µg/m³, the threshold used only to flag values for review.
- **Time zone:** Asia/Karachi (UTC+05:00); timestamps kept tz-aware.
- **Hour labelling (ASSUMPTION, unverified):** timestamps are treated as hour-**ending**, so 00:00 belongs to the previous day. This matches OpenAQ's own file grouping (01:00 … 00:00) but has not been confirmed against AirNow/StateAir documentation. It is configurable via `HOUR_LABEL_CONVENTION` in `src/pm25_qc.py`.
- **Complete hourly grid:** every hour from the first to the last timestamp is represented (50,703 hours), so absent hours count as invalid.
- **Daily completeness:** daily mean (`pm25_daily_mean`) computed only when ≥ 18 of 24 hours are valid. `mean_all_valid_hours` is also kept for transparency.
- **Repeat flag:** a valid hour whose value equals the valid value exactly one hour earlier. Diagnostic only; **nothing was removed** on this basis.

## 4. Coverage (18/24 rule)

Whole record: **2,113 calendar days, 1,464 complete days (69.3%)**. 36,409 of 50,703 hours are valid (71.8%).

| Year | Days | Days with file | Days with ≥1 valid hour | Complete days (≥18/24) | % complete | % hours valid |
|---|---|---|---|---|---|---|
| 2019 (from 05-23) | 223 | 223 | 220 | 208 | 93.3 | 94.7 |
| 2020 | 366 | 363 | 358 | 331 | 90.4 | 92.5 |
| 2021 | 365 | 346 | 279 | 226 | 61.9 | 66.2 |
| 2022 | 365 | 241 | 153 | 99 | 27.1 | 30.0 |
| 2023 | 365 | 320 | 303 | 290 | 79.5 | 79.1 |
| 2024 | 366 | 353 | 315 | 263 | 71.9 | 76.5 |
| 2025 (to 03-04) | 63 | 63 | 49 | 47 | 74.6 | 74.9 |

A daily file existing is not the same as having data. For example, November 2021 has a file for all 30 days but **zero** valid hours.

### Smog season (October–January) complete days

| Season | Days | Complete | % |
|---|---|---|---|
| Oct 2019 – Jan 2020 | 123 | 114 | 92.7 |
| Oct 2020 – Jan 2021 | 123 | 113 | 91.9 |
| Oct 2021 – Jan 2022 | 123 | 70 | 56.9 (all of Nov 2021 missing) |
| Oct 2022 – Jan 2023 | 123 | 37 | 30.1 (0 complete days in Nov and Dec 2022) |
| Oct 2023 – Jan 2024 | 123 | 117 | 95.1 |
| Oct 2024 – Jan 2025 | 123 | 122 | 99.2 |

### Long gaps (≥ 7 consecutive incomplete days): 18 gaps

The largest are 2022-06-06 → 2022-10-03 (120 d), 2022-10-26 → 2023-01-03 (70 d), 2024-04-10 → 2024-05-30 (51 d) and 2021-10-21 → 2021-12-08 (49 d). Full list: `openaq_8664_gaps.csv`.

### Weekly view (Mon–Sun local weeks, full weeks only)

Weeks with 7/7 complete days: 2019: 23 · 2020: 33 · 2021: 15 · 2022: 3 · 2023: 32 · 2024: 34 · 2025: 5. Full distribution: `openaq_8664_weekly_completeness.csv`. **No rule has yet been set** for how many complete days a week needs before a weekly-mean target is valid. That decision is needed before Stage 2.

## 5. Repeated consecutive values

| Year | Valid hours | Repeat hours | % of valid | Runs ≥3 h | Runs ≥6 h | Longest run (h) |
|---|---|---|---|---|---|---|
| 2019 | 5,071 | 106 | 2.1 | 0 | 0 | 2 |
| 2020 | 8,128 | 1,287 | 15.8 | 67 | 1 | 6 |
| 2021 | 5,795 | 959 | 16.5 | 56 | 0 | 4 |
| 2022 | 2,632 | 121 | 4.6 | 4 | 0 | 3 |
| 2023 | 6,932 | 415 | 6.0 | 14 | 0 | 3 |
| 2024 | 6,719 | 617 | 9.2 | 39 | 2 | **120** |
| 2025 | 1,132 | 24 | 2.1 | 0 | 0 | 2 |

### Comparison with the original AirNow data (only window available)
Window 2021-09-10 01:00 → 2021-09-26 00:00, using the single Wayback-archived AirNow file from Stage 1A:

| Source | Valid hours | Repeat hours | % repeats | Mean of valid hours |
|---|---|---|---|---|
| AirNow (original) | 383 | 17 | 4.4% | 60.9 µg/m³ |
| OpenAQ 8664 | 384 | 86 | **22.4%** | 60.0 µg/m³ |

**Interpretation:**
- In this window OpenAQ has about 5× the repeat rate of the original source, while the period mean differs by only ~1.5%.
- This supports, but does not prove, the Stage 1A hypothesis that some hourly values were substituted or duplicated during ingestion.
- The elevated repeat rates in 2020–2021 (≈16%) suggest the artefact may affect those years.
- Effects on daily and weekly means are probably smaller than on individual hours, but **this has not been quantified** beyond the single window above.
- Integer reporting means some genuine repeats are expected (≈4% in the AirNow sample).

### Stuck-value artefact (2024)
From **2024-05-31 07:00 to 2024-06-05 14:00** the value is a constant **67.0 µg/m³**, interrupted only by one `-999` hour. That is a 7-hour run followed by a 120-hour run. Under the current rules this produces **5 days counted as "complete" with a daily mean of exactly 67.0** (2024-05-31 to 2024-06-04). These are almost certainly not real measurements. They have **not** been removed, because no rule for stuck values has been approved yet (see §6).

## 6. Decisions needed before Stage 2

1. **Stuck-value rule:** proposed: invalidate runs of N or more consecutive identical hourly values. With N = 6, three runs are affected: one in 2020 (6 h, value 26.0) and two in 2024 (7 h and 120 h, both 67.0). With N = 7, only the two 2024 runs are affected. The threshold needs your approval.
2. **2020–2021 repeat artefact:** accept OpenAQ hourly values as-is (daily/weekly means may be only mildly affected), or seek further original AirNow data to quantify the bias.
3. **Weekly target validity rule:** minimum complete days per week (e.g. ≥ 5 of 7) for a valid weekly mean.
4. **Hour-labelling convention:** confirm hour-ending vs hour-beginning from StateAir/AirNow documentation.
5. **Data gaps:** 2022 has only 99 complete days, including almost no data from June to December. Walk-forward folds must cope with this, and the smog seasons of 2021–22 and 2022–23 are badly under-represented.
6. **OpenAQ licence/terms:** still unverified (carried over from Stage 1A).

## 7. Output files

| File | Content |
|---|---|
| `data/processed/openaq_8664_hourly_qc.csv` | Complete hourly grid: value, valid, present_in_source, value_valid, repeat_prev, repeat_run_length |
| `data/processed/openaq_8664_daily.csv` | Daily: hours_in_grid, hours_present, hours_valid, mean_all_valid_hours, repeat_hours, complete, pm25_daily_mean |
| `results/tables/openaq_8664_download_manifest.csv` | Per-file key, size, ETag, last-modified, SHA-256 |
| `results/tables/openaq_8664_coverage_by_year.csv` / `_by_month.csv` | Coverage tables |
| `results/tables/openaq_8664_weekly_completeness.csv` | Weeks by number of complete days, per year |
| `results/tables/openaq_8664_repeats_by_year.csv` | Repeat diagnostics |
| `results/tables/openaq_8664_gaps.csv` | Incomplete-day runs ≥ 7 days |
| `results/tables/openaq_8664_qc_summary.json` | Machine-readable summary |
