# Stage 8 — Pre-declared Design: Embargo, Sensitivity, SHAP Stability, Diagnostic and Weekly Ventilation Checks

- **Declared:** 2026-10-25, before any Stage 8 model, score, SHAP value or slope was computed.
- **Status:** approved by the user on 2026-10-25 ("I approve the Stage 8 plan. Commit it and run the analysis."). Committed before any Stage 8 code was run.
- **Purpose:** finish the checks the paper lists as pending (Sections 5.5, 5.6, 5.11, 6.5–6.8):
  1. the one-week embargo forecasts;
  2. the remaining sensitivity analyses;
  3. the stability of the SHAP rankings (H5);
  4. the diagnostic (target-week) experiment, labelled as a non-forecast;
  5. the weekly ventilation slope test of the one-box model.
- **Data:** the Stage 6 record (AirNow, AQS 586PK3010003, **preliminary**; credit the U.S. Department of State and the EPA AirNow program), ERA5, FIRMS VIIRS Suomi NPP standard processing, and the 2,161 HYSPLIT trajectories. No raw data are changed.
- **Unchanged from Stages 3–6 unless stated:** target (eligible Monday–Sunday PKT weekly mean, ≥ 6 of 7 valid days); Random Forest settings (300 trees, min_samples_leaf 5, max_features 0.33, seed 20261021); feature definitions; the k-means trajectory clustering inside each fold (k = 6, n_init 20, seed 20261021, ≥ 365 trajectories); ≥ 52 training weeks; scoring (MAE primary; RMSE, bias, R², skill vs persistence); paired moving-block bootstrap (4-week blocks, 2,000 resamples, seed 20261021); Oct–Jan split by the week's Thursday.
- **Nothing in Stages 1–7 is changed.** Every result below is reported, whatever it shows. No setting is changed after results are seen.

## 1. One-week embargo (primary new result)

The forecast for week T is still issued at 00:00 PKT on Monday at the start of T, but the latest data treated as available end one week earlier, at the **embargo cutoff C = T − 7 days**. Every input must come from before C:

| Input | Zero embargo (Stages 3–6) | One-week embargo (Stage 8) |
|---|---|---|
| PM2.5 history | eligible weeks ending before T; last 4 weeks before T | eligible weeks ending before C; the 4 weeks before C (T−2 … T−5) |
| Age of last week | weeks between source and T | weeks between source and T (so at least 2) |
| Calendar terms | Thursday of T | Thursday of T (the calendar is known in advance) |
| ERA5, FIRMS, mass balance | week T−1 | week T−2 |
| Trajectory features | trajectories of week T−1; k-means fitted before T − 7 d | trajectories of week T−2; k-means fitted on trajectories before C − 7 d, assigned to those before C |
| Training rows | target weeks ending before T, each with its own zero-embargo inputs | target weeks ending before C, each with its own embargo inputs (from two weeks earlier) |
| Persistence | last eligible week ending before T | last eligible week ending before C |
| Climatology | eligible weeks ending before T at the same seasonal position in earlier years | same, restricted to weeks ending before C |
| Ridge PM2.5-history model | inputs and training before T | inputs and training before C |

- **Methods:** persistence, climatology, the Ridge PM2.5-history model, Random Forest layers L1–L5, and L1 + trajectories.
- **Common set:** eligible full weeks for which every embargo method has a forecast.
- **Comparisons**, both for all weeks and for Oct–Jan:
  - each added layer (L2 vs L1, L3 vs L2, L4 vs L3, L5 vs L4);
  - L1 + trajectories vs L1;
  - L5 vs the Ridge model, climatology and persistence.
- **Cost of the embargo:** for each method, MAE with embargo minus MAE without, on weeks where both runs have a forecast, with a paired bootstrap interval.
- **Per-source latency rule: not run.** It would lag each input by its documented delay, but those delays have not been compiled for every source. The FIRMS standard-processing product used here is also not available in near real time. The one-week embargo is used instead as a stricter, uniform test. It covers sources published within a week, such as ERA5's preliminary release (ERA5T), which appears about five days after real time. The paper will state this.

## 2. Sensitivity analyses (zero embargo, one change at a time)

- **Methods in each run:** persistence, climatology, the Ridge model, RF L4 and RF L5.
- **Comparisons**, all weeks and Oct–Jan: L5 vs L4; L5 vs the Ridge model, climatology and persistence.
- **Common set:** each run is scored on its own common set. Runs S1–S3 change the target series, so their numbers of weeks differ from the main run. They are compared with the main run by their conclusions, not by a paired test.

| Run | Change |
|---|---|
| **S1 PM2.5 source** | Target built from AirNow's own daily values (daily_data_v2 files; a day counts as valid if AirNow reports a daily value, using AirNow's own completeness rule) instead of the rebuilt 18-of-24 daily means. Same 6-of-7 weekly rule. |
| **S2 Weekly completeness** | A week is eligible only with all 7 valid days (7 of 7 instead of 6 of 7), for both training targets and evaluation. |
| **S3 Repeated-value rule** | Runs of ≥ 6 identical hourly values are invalid (instead of ≥ 7). Daily and weekly targets rebuilt. |
| **S4 Exclude 2020–2021** | Weeks whose Thursday falls in 2020 or 2021 are removed as training rows and as evaluation weeks. Their PM2.5 may still enter the lagged inputs of early-2022 weeks, because the input data are not in question. |

**Conclusion check (fixed in advance):** a run "agrees with the main result" if:
- the L5 vs L4 interval includes zero;
- L5 vs persistence is negative with an interval that excludes zero;
- L5 vs the Ridge model has an interval that includes zero.

Each run is reported as agreeing or not, criterion by criterion.

**Not possible with the existing data** (stated as limitations, not run):
- other trajectory arrival heights, durations or meteorology (no such trajectories exist);
- an average of neighbouring ERA5 cells (only the single nearest grid point was downloaded);
- the fire-exposure buffer distance, because the forecasts use distance rings, not trajectory buffers. Buffer sensitivity for the association analysis is already reported in Stage 7 (25 and 100 km).

## 3. SHAP stability (H5)

- Out-of-sample exact TreeSHAP for the L5 model, computed exactly as in Stage 5 (each forecast explained by the model trained for that week), in the embargo run and in S1–S4.
- Reported for each run, over its common weeks, and compared with the main run (Stage 5):
  - the six feature-family shares;
  - the top 10 individual features, excluding cluster shares.
- **Stability criterion (fixed in advance):** H5 is supported for SHAP if, in every run:
  - the two largest families are the same two as in the main run (PM2.5 history and calendar);
  - the Spearman rank correlation of the six family shares with the main run is ≥ 0.8.
- The overlap of the top-10 feature lists is reported descriptively.

## 4. Diagnostic experiment (not a forecast)

- **Models:** RF L4-diag and L5-diag. PM2.5 history is exactly as in the forecasts (before T), but the ERA5, FIRMS, mass-balance and trajectory features come from **week T itself**: the observed conditions of the target week.
- Training rows use their own same-week conditions. Trajectory clusters are fitted before T − 7 d, and the trajectories up to the end of week T are assigned to them.
- The target-week PM2.5 is never an input.
- **Reported:** MAE and the paired difference from the forecast L5, all weeks and Oct–Jan, on the common weeks.
- This shows how much error remains even with perfect knowledge of the target week's weather, fires and trajectories: an upper bound on what better weather forecasts could add. It is labelled a diagnostic, non-forecast result everywhere.

## 5. Weekly ventilation slope (Section 5.5 consistency check)

- **Data:** eligible weeks.
- **Model**, within each of the four seasons (by the week's Thursday; winter Dec–Feb, pre-monsoon Mar–May, monsoon Jun–Sep, post-monsoon Oct–Nov): ordinary least squares of log weekly PM2.5 on log weekly mean ventilation coefficient. VC is the mean of hourly ERA5 boundary-layer height × 10 m wind speed over the same week, PKT days, as in `src.mass_balance_features`.
- **Uncertainty:** 95% CI for the slope from a moving-block bootstrap over the season's weeks in time order (4-week blocks, 2,000 resamples, seed 20261025).
- **Interpretation:** a slope near −1 is consistent with PM2.5 scaling as 1/ventilation. This is a same-week association, not a forecast, and not a source estimate.

## 6. Outputs

- **Code:** `src/stage8_robustness.py`, with synthetic-data tests in `tests/test_stage8_robustness.py` (embargo inputs strictly before C; training rows ending before C; diagnostic features from week T; slope recovery on synthetic data).
- **Outputs:** `results/tables/stage8/`. **Report:** `results/tables/stage8_report.md`.
- **Paper:**
  - the PENDING notes in Sections 6.5–6.8 are replaced with these results;
  - Sections 5.5, 5.6 and 5.11 are updated to say what was run and what was not;
  - limitations are updated.
