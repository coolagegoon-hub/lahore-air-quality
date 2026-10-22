# AirNow Rebuild — Lahore Hourly PM2.5 (AQS 586PK3010003)

- **Date:** 2026-10-18
- **Code:** `src/airnow_hourly_series.py` (new). It reuses `src/pm25_qc.py` and `src/stage1c_analysis.py`, both unchanged.
- **Tests:** `tests/test_airnow_hourly_series.py` (9 new tests).
- **Reproduce** (offline; reads the cache built by `src.airnow_bulk`):
  ```bash
  .venv/bin/python -m src.airnow_hourly_series
  .venv/bin/python -m pytest -q tests
  ```
- **Outputs:**
  - `data/processed/airnow_586PK3010003_hourly.csv`: complete hourly grid, 50,400 hours.
  - `data/processed/airnow_586PK3010003_daily_18of24.csv`: daily counts and the 18/24-gated mean.
  - Tables in `results/tables/airnow_rebuild/`.
- **Scope:** Stage 2 was not started. No weekly target was built and no threshold was chosen.
- **Data status:** AirNow data are "preliminary" per the AirNow Data Exchange Guidelines; any results built on them must say so.

## 1. Construction

| Item | Value |
|---|---|
| Source | AirNow `HourlyData_YYYYMMDDhh.dat`, GMT 2019-05-21 00:00 → 2025-02-18 23:00, all 50,424 files (46,872 size-verified; 3,552 cached before verification existed; 0 failed) |
| Time conversion | AirNow time is GMT, hour-beginning [AirNow Hourly Data File fact sheet, Aug 2025] → **hour-ending PKT** = begin + 1 h, converted to Asia/Karachi (UTC+05:00, no DST) |
| Day assignment | `src/pm25_qc.py` unchanged: hour-ending 01:00 … 00:00 = local day (begin-hours 00:00–23:00) |
| Range | Local days 2019-05-22 → 2025-02-18: 2,100 days, 50,400 hours |
| Records in range | 43,212. All are PM2.5, UG/M3, GMT offset 5, site "Lahore", no duplicate hours, values −4 to 974 µg/m³ |
| Validity rule (default) | Record present and value ≥ 0, giving **43,151 valid hours**. The 61 negative values (−4 to −0.1) are invalid under the project rule. |
| Daily rule | ≥ 18 of 24 valid hours, giving **1,777 complete days of 2,100 (84.6%)** |
| Negative-value sensitivity | Keeping values ≥ −5 as valid (AirNow's own practice) gives 1,780 complete days (+3, all in 2024–25). The project rule is unchanged pending your decision. |
| Imputation | None |
| Reporting precision | Values have decimals in 2019 (86%) and 2020 (27%), and are almost all integers from 2021 |

## 2. Time-convention check against AirNow's own daily values [ORIGINAL]

The rebuilt daily means (all valid hours) were compared with AirNow's published `PM2.5-24hr` values on 1,778 days.

| Day grouping | Mean abs. difference | Days within 0.5 µg/m³ |
|---|---|---|
| **Project convention** (hour-ending label − 1 h, i.e. AirNow's "midnight-to-midnight, begin-hour") | **0.083 µg/m³** | **99.5%** |
| Alternative (calendar date of the hour-ending label) | 2.574 µg/m³ | 22.6% |

**Conclusion:** the GMT → hour-ending PKT conversion and the day assignment reproduce AirNow's own daily values. This settles the timestamp question for the AirNow series.

**AirNow's daily completeness (observed, not documented):**
- AirNow published daily values for 3 days with fewer than 18 rebuilt hours: 2024-01-26 (15 h, 117.0), 2024-01-27 (5 h, −1.7) and 2024-01-28 (4 h, −1.9). So AirNow's daily file does **not** apply an 18/24 rule, and it is not a substitute for the rebuilt daily series.
- Two rebuilt complete days have no AirNow daily value: 2020-05-09 and 2022-12-13 (18 and 19 h).

## 3. Comparison with OpenAQ 8664 (same 2,100 local days)

| Metric | AirNow rebuild | OpenAQ 8664 |
|---|---|---|
| Valid hours | **43,151** | 36,409 |
| Complete days (≥ 18/24) | **1,777** | 1,464 |
| Complete in this source only | 318 | 5 |

- **The 5 OpenAQ-only days** are 2024-05-31 … 06-04. That is OpenAQ's constant 67.0 µg/m³ stuck value; AirNow has no record for those days.
- **Daily means on the 1,459 days complete in both:** OpenAQ − AirNow mean difference +0.10 µg/m³, mean absolute difference 2.58, maximum 63.6, Pearson r = 0.9987.

### OpenAQ hour-label alignment, every month [ORIGINAL]
`openaq_alignment_by_month.csv`: share of OpenAQ hours equal (±0.15) to AirNow at the same hour (lag 0) or one hour later (lag +1).

| Period | Pattern |
|---|---|
| 2019-05 → 2019-10 | aligned (≥ 91.5% at lag 0) |
| 2019-11 → 2021-09 | mixed (roughly 30–70% at each lag) |
| 2021-10 → 2023-04 | mostly aligned (2021-12 mixed) |
| 2023-05 → 2023-10 | mixed. In 2023-08 and 2023-09 OpenAQ matches AirNow at no lag from −3 to +3 h (≤ 4.8% at lags −3…0 and +2…+3); hourly correlation 0.28–0.38 in 2023-07…09 and 0.75 in 2023-10 |
| 2023-11 → 2024-02 | shifted one hour early (95.5–100% at lag +1) |
| 2024-03 | mixed |
| 2024-04 → 2025-02 | mostly aligned (2024-10 mixed, 84.8%) |

Counts: 28 months aligned, 32 mixed, 4 shifted, 2 with too few pairs. OpenAQ's hourly values are unreliable in about half the months, while its daily means stay close to AirNow's. The AirNow rebuild has neither problem.

## 4. Coverage of the AirNow rebuild

### By year (local days)

| Year | Days | Complete days (AirNow) | % | Complete days (OpenAQ) | % |
|---|---|---|---|---|---|
| 2019 (from 05-22) | 224 | 220 | 98.2 | 208 | 92.9 |
| 2020 | 366 | 362 | 98.9 | 331 | 90.4 |
| 2021 | 365 | 274 | 75.1 | 226 | 61.9 |
| 2022 | 365 | 241 | 66.0 | 99 | 27.1 |
| 2023 | 365 | 332 | 91.0 | 290 | 79.5 |
| 2024 | 366 | 301 | 82.2 | 263 | 71.9 |
| 2025 (to 02-18) | 49 | 47 | 95.9 | 47 | 95.9 |

### Smog season (October–January) complete days

| Season | Days | AirNow | OpenAQ |
|---|---|---|---|
| 2019-20 | 123 | 121 | 114 |
| 2020-21 | 123 | 121 | 113 |
| 2021-22 | 123 | 72 | 70 |
| **2022-23** | 123 | **98** | **37** |
| 2023-24 | 123 | 117 | 117 |
| 2024-25 | 123 | 122 | 122 |

2021-22 remains poor in both sources: November 2021 has no data in AirNow either.

### Weekly completeness (Mon–Sun, full weeks, Thursday-based year and season; no threshold chosen)

| | Full weeks | 7/7 | ≥ 6/7 | ≥ 5/7 |
|---|---|---|---|---|
| **AirNow, all years** | 299 | **220** | **236** | **246** |
| OpenAQ, same days | 299 | 145 | 178 | 200 |
| **AirNow, smog seasons** | 105 | **84** | **88** | **92** |
| OpenAQ, smog seasons | 105 | 66 | 75 | 79 |

By year (AirNow; 7/7, ≥ 6/7, ≥ 5/7):
- 2019: 28 / 30 / 31 of 31
- 2020: 50 / 52 / 53 of 53
- 2021: 32 / 33 / 35 of 52
- 2022: 24 / 29 / 32 of 52
- 2023: 42 / 44 / 46 of 52
- 2024: 38 / 41 / 42 of 52
- 2025: 6 / 7 / 7 of 7

Per season and year: `weekly_counts_by_smog_season.csv`, `weekly_counts_by_year.csv`.

**Effect on the threshold decision:** with the AirNow rebuild, the 7/7 rule keeps 220 weeks (84 in smog seasons) compared with 145 (66) for OpenAQ, so the gap between thresholds is smaller than in Stage 1C.

## 5. Repeated values in the original source [ORIGINAL vs HEURISTIC]

- Repeat rate in AirNow: 0.5–3.6% of valid hours per year (`airnow_repeat_summary_by_year.csv`). OpenAQ showed 2–17%.
- **Runs of ≥ 6 h in AirNow** [HEURISTIC; the original source itself contains these values, so there is no further source to check against]:
  - 2020-05-03 09:00 → 17:00, 9 h at 24.0 µg/m³;
  - 2024-05-25 03:00 → 08:00, 6 h at 39.0 µg/m³.
- Whether these are real or a stuck instrument cannot be determined from AirNow alone. The S6/S7 run-exclusion decision from Stage 1C still applies, but now affects only these two runs.

## 6. Points for review (nothing decided)

1. **Primary series — DECIDED 2026-10-18:** the AirNow rebuild is the primary PM2.5 series. OpenAQ 8664 is kept for comparison only.
2. **Negative values — DECIDED 2026-10-18:** invalid (project rule), giving 1,777 complete days. Separately, the 2024-01-26 → 28 cluster of near-zero values in mid-winter looks implausible. It is a candidate for a documented plausibility rule [HEURISTIC; not applied; undecided].
3. **Run-exclusion rule (S6/S7):** it now affects only the two AirNow runs listed in §5.
4. **Weekly threshold:** see §4.
5. **Terms:** AirNow data are preliminary. The AirNow Data Exchange Guidelines ask for credit to the U.S. Department of State and the EPA AirNow program, and for agencies to be told about publications (see Stage 1C §5).

## 7. Tests performed
- `.venv/bin/python -m pytest -q tests/test_airnow_hourly_series.py` → **9 passed**. These cover:
  - the hour-ending range and GMT file dates;
  - rejection of wrong units, GMT offset and duplicate hours;
  - the 19:00 GMT → 01:00 PKT conversion;
  - the negative-value policies;
  - grid gaps and the 17/24 vs 24/24 daily rule;
  - month-alignment labels.
- `.venv/bin/python -m pytest -q tests` → **84 passed** (all suites).
- All tests use synthetic data. The real-data numbers above come from one run of `src.airnow_hourly_series`.
