# Stage 6 — Pre-declared Change: Add AirNow's Backfilled September 2022 Data and Rerun Everything

- **Declared:** 2026-10-25, before the PM2.5 record was rebuilt with the new data and before any model, SHAP value or figure was recomputed.
- **Decided by:** the user (2026-10-25: "I am fine with re running everything").
- **Results before this change:** commit `ee4366e` (all tables and figures in `results/` at that commit).

## Why

On 2026-10-23 the AirNow Data Management Center (Marcus Hylton, AirNow DMC Lead, TD Environmental Services) answered the user's question about three gaps in the Lahore record (AQS 586PK3010003):

| Gap | AirNow's explanation |
|---|---|
| 21 Oct – 7 Dec 2021 | AirNow received no data from the monitor; cause unknown to AirNow (State Department contact: DosAir@state.gov). |
| 6 Sep – 1 Oct 2022 | Data exist but were backfilled later, so they are missing from the archived hourly files. AirNow regenerated the month's file. |
| 26 May – 29 Jun 2024 | A mix of unreceived data and data withheld after AirNow QA, because the values did not change from hour to hour (likely a monitor fault). |

Only the 2022 gap can be filled.

## The new data

- **File:** `data/raw/airnow_embassy_historical/Lahore_PM2.5_2022_09_MTD.csv`
- **URL:** https://files.airnowtech.org/airnow/EmbassyHistorical/Lahore/2022/Lahore_PM2.5_2022_09_MTD.csv (given in AirNow's email)
- **Downloaded:** 2026-10-25, HTTP 200, 73,031 bytes; SHA-256 `78a05dfceb810fa529a86f145b2ddb61ff7e8f01e74e0b865c6249b55202871b`
- **Contents:** 683 hourly rows, 2022-09-02 14:00 to 2022-10-01 00:00 (local time); parameter "PM2.5 - Principal", UG/M3, 1-hour duration; QC Name "Valid" for 680 rows and "Missing" (value −999) for 3.
- **Status:** AirNow data, still **preliminary**; credit the U.S. Department of State and the EPA AirNow program.

**Timing check (done before this declaration, no results computed):** the file's `Date (LT)` labels were compared with the existing rebuilt hourly series on the 81 hours both contain. With the labels read as hour-ending PKT (offset 0), all 81 values are identical; offsets of ±1 and ±2 hours match only 3–8 values. The labels are therefore taken as hour-ending PKT, the project's convention.

## Rule (fixed now)

1. Archive rows (`src.airnow_bulk` cache) stay the primary source.
2. A backfill row is used **only for an hour with no archive row**.
3. Where both exist, the values must be identical; any disagreement stops the build (no silent choice).
4. Backfill rows with QC Name other than "Valid", or value −999, are treated as absent (missing), not as values.
5. All later rules apply unchanged: negative values invalid; every hour of a run of ≥ 7 identical consecutive valid values invalid; daily mean needs ≥ 18 of 24 valid hours; weekly mean needs ≥ 6 of 7 valid days (Monday–Sunday PKT).

## What is rerun, unchanged in every other respect

In pipeline order: `airnow_hourly_series`, `stage2_weekly`, `history_model`, `era5_features`, `firms_features`, `mass_balance_features`, `main_model`, `followup_models`, `stage4_trajectory_model`, `shap_analysis`, `figures_data`, `figures_results`; then `pytest`.

All settings declared earlier stay as they were: baselines, Random Forest settings and seed, input layers, trajectory clustering (k = 6, in-fold, seed 20261021), the Stage 3b, 4 and 5 declarations, zero embargo, the 4-week block bootstrap with 2,000 resamples (2 and 8 weeks as checks), the October–January stratum and the common-set rule.

## Reporting

- Every headline number is reported before and after the change, whatever the outcome, in `results/tables/stage6_backfill_report.md`.
- Earlier reports keep their text as the historical record, with a dated note pointing to the new numbers.
- The paper is updated to the new numbers.
- The raw file and this declaration are added to the repository before the rerun, so the order of events is recorded.
