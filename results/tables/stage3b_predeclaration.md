# Stage 3b — Pre-declared Follow-up Models

- **Declared:** 2026-10-21, before any follow-up model was fitted or scored.
- **Requested by:** the user, after seeing Stage 3 (`stage3_model_report.md`).
- **Motivation:** the Stage 3 Random Forest under-predicted high smog-season weeks (bias about −27 µg/m³), while the log-scale Ridge PM2.5-history model was less biased.
- **Status:** these models are reported **alongside** the Stage 3 results and do not replace them. Their scores were not used to choose any setting.

## Unchanged from Stage 3
- Target and eligibility (≥ 6/7 days).
- Cutoff: Monday 00:00 PKT.
- Feature tables and layers L1–L4 (`src.main_model.load_feature_table`).
- Expanding-window walk-forward with ≥ 52 training weeks, refitted for every target week.
- No imputation.
- Common-set scoring (all methods available), with subsets all / smog / non-smog.
- Paired moving-block bootstrap (4-week blocks, 2,000 resamples, seed 20261021).

## Model A — Random Forest on the log scale ("rflog")
- **Target:** log(weekly mean PM2.5).
- **Settings:** same as Stage 3 (300 trees, min_samples_leaf 5, max_features 0.33, seed 20261021), plus `oob_score=True`.
- **Back-transform:** exp(prediction) × Duan smearing factor = mean(exp(y − out-of-bag prediction)) over the training rows of that fold. Out-of-bag predictions are used because in-sample Random Forest residuals are too small.
- **Fitted on:** each layer L1–L4.

## Model B — Ridge with all features of the layer ("ridgeall")
- **Target:** log(weekly mean PM2.5).
- **Fixed transform before scaling** (fitted on nothing, so no leakage): log1p of every `fire_prev_*` count and FRP feature, which are heavily right-skewed.
- **Pipeline:** StandardScaler + Ridge(alpha = 1.0), fitted on training rows only in each fold.
- **Back-transform:** exp × Duan smearing from the training residuals of that fold (as in `src.history_model`).
- **Fitted on:** each layer L1–L4. L1 uses the same features as the existing Ridge PM2.5-history model but within this table and pipeline, so small differences from it can come from the training-set definition.

## Comparisons to report (all of them, whatever their outcome)
1. rflog_L4 vs rf_L4 (Stage 3 model), all and smog.
2. ridgeall_L4 vs Ridge PM2.5-history model, all and smog.
3. rflog_L4 and ridgeall_L4 vs climatology and persistence.
4. Layer increments within each family: L2 vs L1, L3 vs L2, L4 vs L3, all and smog.

## Interpretation rules
- With several comparisons, a single CI excluding 0 is weak evidence. Report all results, and do not pick the best model after the fact as "the" model.
- These are predictive associations only, with no causal claims.
