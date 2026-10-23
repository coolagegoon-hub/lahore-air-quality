# Stage 2 — Weekly PM2.5 Target and Reference Baselines

> **Status update (2026-10-23):** §4 item 3 is done (the PM2.5-history model, §6 of this report). Item 4 is done: ERA5 and FIRMS were downloaded and their features used in Stages 3–5. Items 1–2 (climatology settings, persistence maximum age) are unchanged, as declared. Numbers in this report are unchanged.

- **Date:** 2026-10-20
- **Code:** `src/stage2_weekly.py` (new), which uses `src/airnow_hourly_series.py`, `src/stage1c_analysis.py`, `src/pm25_qc.py`, `src/weekly_targets.py` and `src/baselines.py` unchanged. Tests: `tests/test_stage2_weekly.py` (5 new).
- **Reproduce** (offline):
  ```bash
  .venv/bin/python -m src.stage2_weekly
  .venv/bin/python -m pytest -q tests
  ```
- **Outputs:**
  - `data/processed/pm25_daily_final.csv`: daily, after the run and 18/24 rules.
  - `data/processed/pm25_weekly_target.csv`: the weekly target.
  - Tables in `results/tables/stage2/`.
- **Data:** AirNow, U.S. Consulate Lahore (AQS 586PK3010003). The data are **preliminary**; credit the U.S. Department of State and the EPA AirNow program.
- **No machine-learning model was built.**

## 1. Rules applied (all decided by the user)

| Rule | Setting |
|---|---|
| Primary series | AirNow rebuild, PKT hour-ending, local days 2019-05-22 → 2025-02-18 |
| Negative hourly values | invalid |
| Repeated values | every hour of a run of ≥ 7 identical consecutive valid values is invalid. **9 hours removed:** the 2020-05-03 run at 24.0 µg/m³. The 6-hour run on 2024-05-25 is kept. |
| Daily | ≥ 18 of 24 valid hours, giving **1,776 complete days of 2,100**. The run rule removed one complete day (2020-05-03). |
| Weekly | Monday–Sunday (PKT), eligible when ≥ 6 of 7 days are valid; mean of the valid days |

## 2. Weekly target series

| | Count |
|---|---|
| Weeks touching the record | 301 (2 partial weeks at the ends) |
| Full weeks | 299 |
| **Eligible weeks (≥ 6/7)** | **235**: 220 with 7/7 days, 15 with 6/7 |
| Eligible smog-season weeks (Oct–Jan, by the week's Thursday) | 88 |
| First / last eligible week | 2019-05-27 / 2025-02-10 |
| Range of eligible weekly means | 8.1 – 438.5 µg/m³ |

By year (by each week's Thursday):

| Year | Full weeks | Eligible | Of which 7/7 |
|---|---|---|---|
| 2019 | 31 | 30 | 28 |
| 2020 | 53 | 51 | 50 |
| 2021 | 52 | 33 | 32 |
| 2022 | 52 | 29 | 24 |
| 2023 | 52 | 44 | 42 |
| 2024 | 52 | 41 | 38 |
| 2025 | 7 | 7 | 6 |

**Interpretation note:** 15 eligible weeks are means of 6 observed days. Such a mean is not necessarily the true 7-day mean, and these weeks are flagged (`complete_7_of_7 = False`). In the Stage 1C missing-day experiment on OpenAQ data, a single missing day typically changed a weekly mean by about 3% (95th percentile about 10%).

## 3. Reference baselines (walk-forward)

**Forecast setup:**
- Each week T is forecast at Monday 00:00 PKT at the start of T.
- Only eligible weeks that ended before then are used.
- Neither baseline has fitted parameters, so scoring them week by week is a strict chronological evaluation with no leakage.
- Only eligible observed weeks are scored.

**The baselines:**
- **Persistence:** the most recent eligible week. Age 1 = the previous week; if that week was ineligible, an older week is used. On the 234 eligible targets with a persistence forecast, the source week's age was 1 week for 206 targets, 2–5 weeks for 24, and 7–9 weeks for 4.
- **Seasonal climatology:** the median of eligible weeks within ±2 weeks of the same date in earlier years. It needs at least 4 such weeks from at least 2 earlier years. **These parameters are provisional and were set in advance, not tuned.** Because the record starts in May 2019, climatology is only available from mid-2021.

### Scores (µg/m³; error = prediction − observed)

| Target set | Baseline | n | MAE | RMSE | Bias | Median AE |
|---|---|---|---|---|---|---|
| All eligible targets | Persistence (any age) | 234 | 37.3 | 58.1 | −0.0 | 20.8 |
| Eligible targets with a 1-week-old source | Persistence | 206 | 34.3 | 51.8 | −2.8 | 19.5 |
| Targets where climatology exists | Climatology | 138 | 34.0 | 50.8 | −12.4 | 24.1 |
| **Common set** (both available) | Persistence | 138 | 37.8 | 59.9 | −0.5 | 20.8 |
| **Common set** | Climatology | 138 | 34.0 | 50.8 | −12.4 | 24.1 |
| Common, smog season | Persistence | 54 | 67.0 | 88.1 | −11.0 | 50.8 |
| Common, smog season | Climatology | 54 | 55.5 | 72.3 | −24.0 | 44.2 |
| Common, non-smog | Persistence | 84 | 19.1 | 30.0 | +6.3 | 12.3 |
| Common, non-smog | Climatology | 84 | 20.3 | 29.6 | −5.0 | 12.7 |

### What these numbers show (and do not show)
- **The bar for later models.** On the common set, climatology has the lower MAE and RMSE (34.0 / 50.8 vs 37.8 / 59.9). Persistence has the lower median error (20.8 vs 24.1) and almost no average bias.
- **Errors are much larger in the smog season** (MAE 55–67 µg/m³) than outside it (19–20). That is where a model would need to add the most.
- **Climatology underpredicts on average** (bias −12.4; −24.0 in the smog season). This is a property of these weeks and this baseline, not evidence of a long-term change. AirNow's data-use guidelines also advise against using these preliminary data to assess trends.
- **Small samples.** 138 common weeks (54 in the smog season) span 2021–2025, and differences of a few µg/m³ between baselines may not be meaningful. No significance test was run.
- These are **predictive** comparisons only; they say nothing about causes.

## 4. Open items (for review; nothing decided)
1. **Climatology parameters** (±2 weeks, ≥ 2 years, ≥ 4 weeks) are provisional. Changing them after seeing these scores would be tuning on the evaluation period, so any change should be justified in advance.
2. **Persistence source age:** 28 forecasts used a source week 2–9 weeks old. A maximum age (e.g. 2 weeks) is a design choice; the scores for age-1-only forecasts are shown above.
3. **The third baseline** required by CLAUDE.md, a PM2.5-history-only model, is not built. It needs fitting inside walk-forward folds.
4. **Next stage:** the input data (ERA5, FIRMS, HYSPLIT). You need to create the ERA5 (Copernicus) account and get a NASA FIRMS key.

## 5. Tests performed
- `.venv/bin/python -m pytest -q tests/test_stage2_weekly.py` → **5 passed**. These cover:
  - a 7-h run excluded before the daily rule, while a 6-h run is kept;
  - the 6/7 weekly threshold and Thursday-based smog flag;
  - the score metrics;
  - scoring restricted to eligible observed weeks.
- `.venv/bin/python -m pytest -q tests` → **89 passed** (all suites).
- All tests use synthetic data. The real-data numbers above come from one run of `src.stage2_weekly`.

## 6. PM2.5-history baseline model (added 2026-10-20)

**Code:** `src/history_model.py`. Run it with `.venv/bin/python -m src.history_model` after `src.stage2_weekly`. Tests: `tests/test_history_model.py` (5).

**Design (fixed before any results were seen; not tuned):**
- **Features:** only eligible weeks that ended before week T's cutoff, within the previous 4 weeks:
  - log of the most recent weekly mean and its age in weeks;
  - log of the mean of those weeks, and how many there were;
  - 2 annual sine/cosine harmonics of the target week's date (calendar only).
- **Target:** log weekly mean.
- **Model:** StandardScaler + Ridge (alpha 1.0), refitted from scratch for every target week on earlier weeks only (expanding window).
- **Back-transform:** exponentiated, with a Duan smearing correction computed from the same training rows.
- **Minimum training:** 52 weeks.
- **No forecast when:** there is no eligible week in the last 4 weeks (17 targets), or before 52 training weeks exist (54 targets). 228 targets got a forecast. No randomness is involved.

**Scores on the 133 eligible weeks where all three baselines forecast** (µg/m³; error = prediction − observed):

| Subset | Baseline | n | MAE | RMSE | Bias | Median AE |
|---|---|---|---|---|---|---|
| All | Persistence | 133 | 36.4 | 57.9 | +0.4 | 19.5 |
| All | Climatology | 133 | 33.7 | 50.3 | −11.6 | 24.5 |
| All | **History model** | 133 | **30.5** | **47.1** | −4.8 | **16.9** |
| Smog season | Persistence | 52 | 64.9 | 85.1 | −6.7 | 50.8 |
| Smog season | Climatology | 52 | 55.8 | 72.8 | −23.6 | 44.2 |
| Smog season | History model | 52 | 56.1 | 70.9 | −10.5 | 45.7 |
| Non-smog | Persistence | 81 | 18.1 | 29.3 | +4.9 | 11.6 |
| Non-smog | Climatology | 81 | 19.5 | 27.3 | −3.9 | 13.0 |
| Non-smog | History model | 81 | 14.1 | 20.4 | −1.2 | 11.2 |

**Reading:**
- On this common set the history model has the lowest MAE and RMSE overall and outside the smog season.
- In the smog season it is about level with climatology (MAE 56.1 vs 55.8; RMSE 70.9 vs 72.8).
- The smog-season gap is the target for the ERA5 and FIRMS inputs. Any later model must beat all three baselines on the same weeks.
- The sample is small (133 weeks; 52 in smog seasons) and no significance test was run. These are predictive comparisons only.
- The data are preliminary AirNow data.

**Validated-data check:** AirNow's embassy map states that readings are preliminary and unvalidated. A 2019 study of 29 U.S. diplomatic posts (Atmospheric Environment, https://www.sciencedirect.com/science/article/abs/pii/S1352231019303838) is reported in search results to describe BAM-1020 monitors and AirNow QC checks. **[UNVERIFIED]:** the article was not accessible (HTTP 403). No validated version of the Lahore record was found.
