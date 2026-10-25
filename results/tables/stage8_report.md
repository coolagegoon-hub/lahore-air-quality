# Stage 8 — Embargo, Sensitivity, SHAP Stability, Diagnostic and Weekly Ventilation Checks: Results

- **Date:** 2026-10-25
- **Design:** pre-declared in `stage8_predeclaration.md`, approved by the user and committed (`060cccd`) before any Stage 8 code was run. Nothing was changed after results were seen, and every pre-declared result is reported.
- **Code:** `src/stage8_robustness.py` (tests: `tests/test_stage8_robustness.py`, 6). **Outputs:** `results/tables/stage8/`.
- **Data:** PM2.5 is AirNow (U.S. Department of State / EPA AirNow), **preliminary**; Stage 6 record. All values are in µg m⁻³ unless stated.
- **Reproduction check:** with embargo 0 and week T−1 inputs, the Stage 8 engine reproduced the saved Stage 2–4 forecasts (persistence, climatology, Ridge, RF L4, RF L5) to within 5 × 10⁻⁷ µg m⁻³, the rounding of the saved files.
- **One correction during the run:** the first run stopped with a column-name error after the embargo models, while it was reading the earlier zero-embargo forecasts. The code was fixed to read them from the Stage 4 file and the whole stage was rerun from the start. No setting changed.

## 1. One-week embargo

136 common weeks (17 May 2021 to 10 February 2025; 52 in Oct–Jan).

| Method | MAE | RMSE | R² | Bias | Skill | MAE Oct–Jan | Bias Oct–Jan | MAE other |
|---|---|---|---|---|---|---|---|---|
| Persistence | 46.1 | 73.0 | 0.37 | +1.6 | 0.00 | 83.5 | −11.8 | 22.9 |
| Climatology | 31.5 | 47.1 | 0.74 | −9.8 | 0.32 | **52.4** | −20.1 | 18.6 |
| Ridge, PM2.5 history | 32.4 | 51.3 | 0.69 | −6.6 | 0.30 | 59.5 | −15.3 | 15.7 |
| RF 1: PM2.5 history | 30.5 | 49.2 | 0.72 | −10.1 | 0.34 | 55.1 | −35.5 | **15.2** |
| RF 2: + ERA5 | 31.2 | 49.7 | 0.71 | −9.7 | 0.32 | 54.1 | −34.0 | 17.0 |
| RF 3: + fire | 31.5 | 49.9 | 0.71 | −10.0 | 0.32 | 54.6 | −33.6 | 17.2 |
| RF 4: + mass balance | 32.8 | 50.5 | 0.70 | −9.6 | 0.29 | 55.7 | −34.3 | 18.6 |
| RF 5: + trajectories | 32.2 | 50.0 | 0.71 | −9.9 | 0.30 | 55.5 | −34.2 | 17.8 |
| RF 1 + trajectories | **30.3** | 49.2 | 0.72 | −10.9 | **0.34** | 54.7 | −36.7 | 15.2 |

**Paired differences in MAE (4-week blocks, 95% CI)**

| Comparison | All weeks | Oct–Jan |
|---|---|---|
| RF 2 − RF 1 (ERA5) | +0.7 (−1.2 to +2.8) | −1.0 (−5.5 to +2.7) |
| RF 3 − RF 2 (fire) | +0.3 (−0.7 to +1.0) | +0.5 (−1.0 to +1.9) |
| RF 4 − RF 3 (mass balance) | **+1.3 (+0.4 to +2.2)** | +1.1 (−0.6 to +3.1) |
| RF 5 − RF 4 (trajectories) | −0.6 (−1.2 to +0.2) | −0.2 (−1.7 to +1.5) |
| RF 1 + traj − RF 1 | −0.1 (−1.0 to +1.0) | −0.4 (−2.9 to +2.0) |
| RF 5 − Ridge | −0.2 (−5.5 to +3.5) | −4.0 (−14.7 to +5.1) |
| RF 5 − climatology | +0.7 (−2.8 to +3.8) | +3.2 (−2.3 to +9.5) |
| RF 5 − persistence | **−13.8 (−23.1 to −6.3)** | **−28.0 (−46.3 to −10.2)** |

**Cost of the embargo** (same method, embargo minus zero embargo, on weeks where both forecast):
- Persistence: +10.5 (+5.8 to +15.6; 237 weeks).
- Ridge: +3.5 (+1.2 to +5.7).
- RF 1 to RF 5: between +3.2 and +5.1, every interval above zero (177 weeks). RF 5 was +5.1 (+2.3 to +8.3).
- Climatology: unchanged, because its inputs come from earlier years.
- In Oct–Jan, the losses are +5.8 to +7.6 for the models and +17.3 for persistence.

**Reading:**
- A week's delay in data costs every model that relies on recent PM2.5 about 3 to 5 µg m⁻³ of MAE.
- No added input group improves the embargoed forecasts. The mass-balance layer makes them slightly but reliably worse.
- The full model still beats persistence clearly, but it is no better than climatology or the Ridge model.
- The best embargoed models are the forests built on PM2.5 history (with or without trajectories). Their MAE of about 30 is barely better than climatology's 31.5.
- The trajectory features' advantage is not reliable under either embargo.

**Per-source latency rule:** not run, as declared.

## 2. Sensitivity analyses (zero embargo)

| Run | Eligible weeks | Common weeks | MAE RF 5 (RF 4, Ridge, persistence) | RF 5 − RF 4 | RF 5 − Ridge | RF 5 − persistence | Agrees with main? |
|---|---|---|---|---|---|---|---|
| Main (Stages 4–6) | 239 | 138 | 28.3 (28.7, 29.7, 35.5) | −0.4 (−1.3 to +0.8) | −1.3 (−5.4 to +1.7) | −7.1 (−12.7 to −2.5) | — |
| S1 AirNow daily values | 235 | 131 | 29.1 (29.0, 30.0, 35.0) | +0.1 (−0.8 to +1.3) | −0.8 (−5.3 to +2.2) | −5.9 (−11.8 to −0.6) | Yes |
| S2 7 of 7 days | 223 | 124 | 29.0 (29.3, 31.2, 36.0) | −0.3 (−1.4 to +0.9) | −2.2 (−6.7 to +0.9) | −7.0 (−13.3 to −2.0) | Yes |
| S3 6-hour run rule | 239 | 138 | 28.4 (28.7, 29.7, 35.5) | −0.4 (−1.3 to +0.8) | −1.3 (−5.4 to +1.7) | −7.1 (−12.7 to −2.5) | Yes |
| S4 exclude 2020–2021 | 155 | 99 | 35.5 (35.8, 35.1, 37.8) | −0.4 (−1.1 to +0.4) | +0.3 (−4.3 to +3.8) | −2.3 (−9.9 to +4.0) | **No** |

- **S3:** the 6-hour rule removed 15 hours (against 9 for the 7-hour rule). No week changed eligibility, and the results are almost identical to the main run.
- **S4:** two of the three criteria hold:
  - the trajectory layer still gives no reliable gain;
  - the full model is still not reliably better than the Ridge model;
  - but its advantage over persistence is no longer reliable (−2.3, interval −9.9 to +4.0).

  Without 2020 and 2021, evaluation covers 2022 to February 2025 with fewer training weeks early on, and every method's MAE is higher.

**Not run, as declared:** other trajectory heights, durations or meteorology; neighbouring ERA5 cells; the fire buffer for forecasts (buffer sensitivity for the association analysis is in Stage 7).

## 3. SHAP stability (H5)

Family shares (% of total mean |SHAP|, over each run's common weeks), compared with the main run (Stage 5):

| Run | PM2.5 history | Calendar | ERA5 | Mass balance | Fire | Trajectories | Spearman ρ | Top two same? | Top-10 overlap | Stable? |
|---|---|---|---|---|---|---|---|---|---|---|
| Main | 38.0 | 25.9 | 15.6 | 8.6 | 8.3 | 3.7 | — | — | — | — |
| Embargo | 19.1 | 37.1 | 16.9 | 17.7 | 7.5 | 1.7 | 0.89 | Yes | 7 | Yes |
| S1 | 39.2 | 25.5 | 14.7 | 9.0 | 8.6 | 3.1 | 1.00 | Yes | 10 | Yes |
| S2 | 39.0 | 24.3 | 15.7 | 9.2 | 8.5 | 3.3 | 1.00 | Yes | 9 | Yes |
| S3 | 38.0 | 25.9 | 15.6 | 8.6 | 8.3 | 3.7 | 1.00 | Yes | 10 | Yes |
| S4 | 17.8 | 25.5 | **41.2** | 7.4 | 6.5 | 1.7 | 0.77 | **No** | 6 | **No** |

- All SHAP values added up to their predictions (largest error 4.5 × 10⁻¹³).
- **H5 (SHAP part) is not supported in every run.** The rankings are stable under the embargo and S1–S3, but not in S4. Without 2020–2021, the model leaned most on ERA5 pressure and temperature, and the share of PM2.5 history halved.
- Under the embargo, the calendar became the largest family, and the low-ventilation hours feature rose to third place among single features.
- Trajectories stayed the smallest family in every run (1.7 to 3.7%).

## 4. Diagnostic experiment (NOT a forecast)

182 common weeks (15 June 2020 to 10 February 2025; 70 in Oct–Jan). These are more weeks than the forecast comparison because climatology is not part of this set.

| Model | MAE | R² | MAE Oct–Jan |
|---|---|---|---|
| Persistence | 36.7 | 0.61 | 65.0 |
| RF 5 forecast (week T−1 inputs) | 29.9 | 0.74 | 51.0 |
| RF 4-diag (week T conditions) | 23.8 | 0.83 | 40.6 |
| RF 5-diag (week T conditions) | 24.0 | 0.83 | 41.1 |

- RF 5-diag − RF 5 forecast: −5.9 (−9.7 to −2.2) over all weeks and −9.9 (−18.1 to −2.8) in Oct–Jan.
- Knowing the target week's actual weather, fires and trajectories would cut the error by about a fifth.
- Even with that knowledge, the error in Oct–Jan is still about 41 and the model still under-predicts (bias −16).
- Target-week trajectories add nothing beyond target-week weather (24.0 against 23.8).

## 5. Weekly ventilation slope (same-week association)

| Season | Weeks | Slope of log PM2.5 on log VC (95% CI) |
|---|---|---|
| Winter | 61 | −0.58 (−0.76 to −0.41) |
| Pre-monsoon | 49 | +0.09 (−0.28 to +0.39) |
| Monsoon | 86 | +0.12 (−0.14 to +0.27) |
| Post-monsoon | 43 | −0.85 (−1.15 to −0.63) |

- At weekly resolution, the slope is closer to the box-model value of −1 than the daily slopes (Stage 7: about −0.47). In the post-monsoon season, its interval includes −1.
- In the pre-monsoon and monsoon seasons, there is no association.
- This is a same-week association, consistent with PM2.5 scaling with 1/ventilation in the polluted seasons. It is not a source estimate.
