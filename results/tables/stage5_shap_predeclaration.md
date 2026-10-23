# Stage 5 — Pre-declared Design: SHAP Analysis of the Layer-5 Model

- **Declared:** 2026-10-23, before any SHAP value was computed.
- **Model explained:** RF L5 (`rf_L5_plus_traj`, k = 6), exactly as in Stage 4 (`stage4_predeclaration.md`, `src/stage4_trajectory_model.py`).
- **Tool:** `shap` 0.54.1, `TreeExplainer`, default `tree_path_dependent` feature perturbation (exact for tree ensembles; no background sample needed).
- **Purpose (CLAUDE.md interpretation rules):** SHAP shows which inputs **the model relied on** for its forecasts. It is **not** causal source attribution, and it is not evidence of what causes Lahore's PM2.5.

## Method
1. **Fold-by-fold, out-of-sample.** For every target week T, the model is refitted exactly as in Stage 4: same expanding window, same fold-specific k-means (fitted on trajectories before T − 7 days), same RF settings and seed. SHAP values are then computed for **week T's forecast only**, with that fold's model. One SHAP vector per forecast; no model ever explains data it was trained on.
2. **Reproduction check:** the refitted predictions must equal the saved Stage 4 `rf_L5_plus_traj` predictions (to 1e-6), or the run is rejected. Additivity: base value + Σ SHAP = prediction, to 1e-6.
3. **Feature groups** (every feature in exactly one group):

   | Group | Features |
   |---|---|
   | PM2.5 history | log_last, age_last, log_mean4, n_recent |
   | Calendar (season) | sin1, cos1, sin2, cos2 |
   | ERA5 weather | all `era5_prev_*` (21) |
   | Fire (FIRMS) | all `fire_prev_*` (10) |
   | Mass balance | all `mb_prev_*` (5) |
   | Trajectories | `traj_frac_c1–c6` + traj_mean_dist72_km, traj_frac_pts_east_se, traj_mean_height_m |

4. **Group SHAP:** for each forecast, the sum of SHAP values of the group's features (SHAP is additive, so this is the group's contribution). Report:
   - mean |group SHAP|;
   - its share of the total mean |SHAP|;
   - mean signed group SHAP.
5. **Weeks reported:** the Stage 4 common set (133 eligible weeks, 2021-05-17 → 2025-02-10), all weeks / Oct–Jan / other months. The same split is used as in Stages 3–4; the four-season scheme is pending.
6. **Individual features:** the top 10 by mean |SHAP|, **excluding** the six cluster-share features. Their labels change meaning between folds, so they are reported only inside the trajectory group. A caution travels with the list: correlated features (e.g. temperature, mixing height and ventilation) share credit somewhat arbitrarily.
7. **Figure:** grouped bars of mean |group SHAP|, all weeks vs Oct–Jan.

## Not changed by this stage
Model, data, embargo (zero) and all earlier results. If the embargo or season choices change later, this analysis is rerun.
