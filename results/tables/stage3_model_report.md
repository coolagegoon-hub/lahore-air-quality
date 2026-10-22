# Stage 3 — Main Model (Random Forest) Built Up in Input Layers

- **Date:** 2026-10-21
- **Code:** `src/main_model.py`; tests `tests/test_main_model.py` (4).
- **Reproduce:**
  ```bash
  .venv/bin/python -m src.main_model
  ```
  Run it after `src.stage2_weekly`, `src.history_model`, `src.era5_features`, `src.firms_features` and `src.mass_balance_features`.
- **Outputs:** `results/tables/stage3/` (`predictions.csv`, `scores_common_set.csv`, `mae_difference_bootstrap.csv`, `stage3_summary.json`).
- **Data:** PM2.5 is AirNow (U.S. Department of State / EPA AirNow); it is **preliminary**.
- **Not yet included:** HYSPLIT. It will be added as layer 5.

## 1. Design (fixed before results; nothing tuned on the evaluation period)

**Target:** eligible weekly mean PM2.5 (≥ 6 of 7 valid days), forecast at Monday 00:00 PKT.

**Input layers (cumulative):**

| Layer | Inputs | Features |
|---|---|---|
| L1 | PM2.5 history: last eligible week (log), its age, 4-week mean (log), count, annual harmonics | 8 |
| L2 | + ERA5 previous-week weather | 29 |
| L3 | + FIRMS previous-week fires (VIIRS SNPP rings and sectors) | 39 |
| L4 | + one-box mass-balance (ventilation) features | 44 |

**Model:** Random Forest (300 trees, min_samples_leaf = 5, max_features = 0.33, seed 20261021). It is trained on the raw weekly mean and refitted from scratch for every forecast week, on eligible weeks that ended before the forecast (expanding window, at least 52 training weeks). There is no imputation, and no preprocessing is fitted.

**Comparison set:** 133 eligible weeks (52 in the smog season, Oct–Jan) on which all seven methods produced a forecast, from mid-2021 to February 2025.

**Uncertainty:** paired moving-block bootstrap of MAE differences (4-week blocks, 2,000 resamples, fixed seed).

## 2. Scores (µg/m³; error = prediction − observed)

| Subset | Method | MAE | RMSE | Bias | Median AE |
|---|---|---|---|---|---|
| All (133) | Persistence | 36.4 | 57.9 | +0.4 | 19.5 |
| | Climatology | 33.7 | 50.3 | −11.6 | 24.5 |
| | Ridge PM2.5-history | 30.5 | **47.1** | −4.8 | 16.9 |
| | RF L1 history | 30.2 | 48.6 | −9.2 | 17.9 |
| | RF L2 + ERA5 | 29.8 | 48.2 | −8.1 | 17.5 |
| | RF L3 + fire | 29.4 | 48.6 | −8.1 | **15.1** |
| | **RF L4 + mass balance** | **29.3** | 48.7 | −7.6 | 15.7 |
| Smog (52) | Persistence | 64.9 | 85.1 | −6.7 | 50.8 |
| | Climatology | 55.8 | 72.8 | −23.6 | 44.2 |
| | Ridge PM2.5-history | 56.1 | **70.9** | −10.5 | 45.7 |
| | RF L1 | 53.2 | 73.5 | −30.4 | 38.7 |
| | RF L2 | 51.3 | 72.7 | −27.6 | **37.1** |
| | RF L3 | 52.2 | 73.7 | −27.6 | 40.5 |
| | **RF L4** | **51.1** | 73.7 | −26.7 | 38.5 |
| Non-smog (81) | Ridge PM2.5-history | **14.1** | 20.4 | −1.2 | 11.2 |
| | RF L4 | 15.3 | 20.2 | +4.7 | 10.9 |

## 3. Is each improvement real? (MAE difference, negative = first model better; 95% block-bootstrap CI)

| Comparison | Subset | ΔMAE | 95% CI | Interpretation |
|---|---|---|---|---|
| RF L4 vs persistence | all | −7.1 | −12.9 to −2.3 | better; CI excludes 0 |
| RF L4 vs persistence | smog | −13.8 | −25.7 to −2.5 | better; CI excludes 0 |
| RF L4 vs climatology | all | −4.4 | −8.3 to −1.8 | better; CI excludes 0 |
| RF L4 vs climatology | smog | −4.8 | −10.7 to +0.7 | inconclusive |
| RF L4 vs Ridge history | all | −1.2 | −6.4 to +2.4 | inconclusive |
| RF L4 vs Ridge history | smog | −5.0 | −15.2 to +4.4 | inconclusive |
| + ERA5 (L2 vs L1) | all | −0.4 | −2.3 to +1.1 | inconclusive |
| + ERA5 | smog | −1.9 | −5.6 to +2.1 | inconclusive |
| + fire (L3 vs L2) | all | −0.4 | −1.6 to +0.6 | inconclusive |
| + fire | smog | +0.9 | −0.8 to +2.8 | inconclusive (slightly worse) |
| + mass balance (L4 vs L3) | all | −0.1 | −1.0 to +0.7 | inconclusive |
| + mass balance | smog | −1.2 | −3.1 to +0.3 | inconclusive (95% of resamples below 0) |

## 4. What the results show (honest reading)

1. **The full model clearly beats the two simplest baselines** (persistence and climatology) over all weeks, and persistence in the smog season too.
2. **It does not clearly beat the PM2.5-history Ridge model.** The MAE is 1.2 µg/m³ lower, but the uncertainty range includes zero, and its RMSE is slightly higher (48.7 vs 47.1).
3. **Each added input layer lowers MAE a little** (about 0.1–0.4 µg/m³ overall; up to 1.9 in the smog season for ERA5). None of these gains is statistically distinguishable from zero with 133 weeks. Fire inputs slightly worsened smog-season MAE.
4. **Main weakness: the Random Forest under-predicts high-pollution weeks** (smog-season bias about −27 to −30 µg/m³). Tree models cannot predict above the values they were trained on, and early training windows contain few extreme weeks. The Ridge model, which works on the log scale, is less biased (−10.5).
5. **These are predictive comparisons only.** They do not show that weather, fires or ventilation cause the PM2.5 changes.

**Limitations:** 133 comparison weeks (52 in the smog season); one monitor; preliminary AirNow data; ERA5 used as a stand-in for real-time analyses; FIRMS cannot see fires under cloud; HYSPLIT not yet included.

## 5. Open decisions (nothing changed after seeing results)

Any of these would be a **new, pre-declared analysis**, reported alongside the current one rather than replacing it, because choosing after seeing the test results risks overfitting the evaluation period:
- Add HYSPLIT as layer L5 (planned).
- Fit the Random Forest on the log scale, or add a second model type (e.g. gradient boosting or Ridge with all features), to address the under-prediction of high weeks.
- SHAP analysis of the final model (planned). It shows associations the model uses, not causes.

## 6. Pre-declared follow-up models (Stage 3b, added 2026-10-21)

**Declaration:** written before fitting, in `results/tables/stage3b_predeclaration.md`.
**Code:** `src/followup_models.py`; tests `tests/test_followup_models.py` (5).
**Outputs:** `results/tables/stage3b/`.
**Scope:** same 133-week common set as above. All declared comparisons are reported below.

**The two models:**
- **rflog:** Random Forest on log PM2.5, with out-of-bag smearing.
- **ridgeall:** Ridge on log PM2.5 using all features of the layer (fire features log1p-transformed).

| Subset | Method | MAE | RMSE | Bias |
|---|---|---|---|---|
| All | rf_L4 (Stage 3) | 29.3 | 48.7 | −7.6 |
| All | rflog L1 / L2 / L3 / L4 | 30.0 / 30.2 / 29.4 / 29.6 | 48.9 / 48.8 / 48.5 / 48.6 | −11.1 / −9.2 / −8.6 / −7.9 |
| All | ridgeall L1 / L2 / L3 / L4 | 30.5 / 32.9 / 32.6 / 34.3 | 47.1 / 51.2 / 50.8 / 56.2 | −4.8 / −2.3 / −0.9 / −0.1 |
| Smog | rf_L4 (Stage 3) | 51.1 | 73.7 | −26.7 |
| Smog | rflog L4 | 52.6 | 74.0 | −25.8 |
| Smog | ridgeall L4 | 60.9 | 84.5 | +3.7 |

ridgeall L1 reproduces the Ridge PM2.5-history model exactly (same features, same training weeks), which is a consistency check.

**Declared comparisons (ΔMAE, 95% block-bootstrap CI; negative = first better):**

| Comparison | All | Smog |
|---|---|---|
| rflog L4 vs rf L4 | +0.3 (−0.5, +1.5) | +1.6 (−0.6, +3.8) |
| rflog L4 vs Ridge history | −0.9 (−5.7, +2.5) | −3.5 (−12.7, +5.2) |
| rflog L4 vs climatology | **−4.1 (−8.2, −1.2)** | −3.2 (−9.5, +2.5) |
| rflog L4 vs persistence | **−6.8 (−12.3, −1.9)** | **−12.2 (−23.3, −1.7)** |
| ridgeall L4 vs Ridge history | +3.7 (−1.7, +10.4) | +4.8 (−8.9, +20.5) |
| ridgeall L4 vs climatology | +0.6 (−5.3, +7.3) | +5.0 (−10.4, +21.2) |
| ridgeall L4 vs persistence | −2.2 (−8.3, +4.7) | −4.0 (−17.1, +9.7) |
| rflog: +ERA5 / +fire / +mass balance | +0.2 / −0.8 / +0.2 (all CIs include 0) | −0.8 / −0.6 / +0.3 (all include 0) |
| ridgeall: +ERA5 / +fire / +mass balance | +2.4 / −0.3 / +1.6 (all CIs include 0) | +2.9 / −0.2 / +2.1 (all include 0) |

**Reading:**
1. **The log scale did not fix the under-prediction of smog peaks** (bias −25.8 vs −26.7) and did not improve accuracy (MAE 29.6 vs 29.3; difference inconclusive). The limitation therefore does not come mainly from the target scale.
2. **Ridge with all features got worse as inputs were added** (MAE 30.5 → 34.3; RMSE 47.1 → 56.2), consistent with overfitting many correlated weather features with about 52–230 training weeks. Its bias is close to zero, but its errors are larger.
3. **The overall picture is unchanged:**
   - every model beats persistence;
   - the tree models beat climatology overall;
   - no model reliably beats the simple Ridge PM2.5-history model;
   - none of the added inputs (ERA5, fires, mass balance) shows a reliable gain in any model family.
4. Several comparisons were run, so the few CIs that exclude 0 should be read cautiously. This is association and prediction only, not causation.
