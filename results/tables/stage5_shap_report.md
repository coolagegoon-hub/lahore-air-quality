# Stage 5 — SHAP Analysis of the Layer-5 Model: Results

> **Status update (2026-10-25):** the numbers below were recomputed after AirNow's backfilled September 2022 data were added (pre-declared in `stage6_backfill_predeclaration.md`). Current numbers and a before/after comparison: `stage6_backfill_report.md`. The text below is kept as the historical record.

- **Date:** 2026-10-23
- **Design:** pre-declared in `stage5_shap_predeclaration.md` (commit 5e8ef42, before computing). No setting was changed after seeing results.
- **Code:** `src/shap_analysis.py`; tests `tests/test_shap_analysis.py` (4).
- **Outputs:** `results/tables/stage5/`, figure `results/figures/fig5_shap_groups.png|pdf`.
- **Model explained:** RF L5 (all inputs, k = 6), zero embargo. PM2.5 is AirNow (U.S. Department of State / EPA AirNow); the data are **preliminary**.
- **Interpretation:** SHAP describes **what the model relied on** for its forecasts. It is not causal source attribution and does not show what causes Lahore's PM2.5.

## 1. Method and checks
- **Forecasts explained:** 228 walk-forward forecasts, each by `shap.TreeExplainer` (v0.54.1) applied to **that week's own model**, so every explanation is out-of-sample.
- **Reproduction check:** the refitted models reproduce the saved Stage 4 forecasts; maximum difference 4.9 × 10⁻⁷ µg/m³ (tolerance 10⁻⁶). ✓
- **Additivity check:** base value + Σ SHAP = prediction; maximum error 2.6 × 10⁻¹³. ✓
- **Weeks reported:** the Stage 4 common set: 133 eligible weeks (52 Oct–Jan, 81 other months).

## 2. Reliance by input group (mean |group SHAP|, µg/m³; share of total in brackets)

| Group | All weeks (133) | Oct–Jan (52) | Other months (81) |
|---|---|---|---|
| PM2.5 history | 27.9 (37.6%) | 35.4 (36.7%) | 23.1 (38.5%) |
| Calendar (season) | 19.2 (25.8%) | 26.6 (27.6%) | 14.4 (24.0%) |
| ERA5 weather | 11.6 (15.6%) | 15.1 (15.7%) | 9.3 (15.5%) |
| Mass balance | 7.0 (9.4%) | 9.0 (9.3%) | 5.7 (9.6%) |
| Fire (FIRMS) | 6.0 (8.0%) | 5.8 (6.0%) | 6.1 (10.1%) |
| Trajectories | 2.7 (3.6%) | 4.6 (4.7%) | 1.5 (2.4%) |

**Mean signed group SHAP:** in Oct–Jan every group pushes forecasts **up** (history +27.0, season +25.2, weather +13.8, mass balance +8.5, fire +4.4, trajectories +2.2 µg/m³). In other months history, season and weather push them **down**. This is consistent with the seasonal cycle.

## 3. Top individual inputs (mean |SHAP|, µg/m³; cluster shares excluded)

| Rank | All weeks | Oct–Jan |
|---|---|---|
| 1 | cos1, annual season term (19.1) | cos1 (25.1) |
| 2 | log_last, last week's PM2.5 (17.6) | log_last (22.5) |
| 3 | log_mean4, 4-week mean PM2.5 (10.6) | log_mean4 (13.1) |
| 4 | low-ventilation hours (4.1) | low-ventilation hours (4.9) |
| 5 | boundary-layer height (2.8) | surface pressure (3.8) |
| 6 | surface pressure (2.7) | boundary-layer height (3.5) |
| 7 | mean sea-level pressure (2.3) | mean trajectory height (3.4) |
| 8 | sin1 (2.1) | mean sea-level pressure (3.1) |
| 9 | mean trajectory height (2.0) | sin1 (2.7) |
| 10 | sin2 (1.6) | rainfall (2.4) |

**Caution:** several of these inputs are strongly correlated (pressure variables; mixing height and ventilation; the season terms and temperature). SHAP divides credit among correlated inputs somewhat arbitrarily, so individual ranks are less reliable than group totals.

## 4. Reading
1. **The model relies mostly on recent PM2.5 and the time of year** (about 63% of total reliance combined). This matches Stages 3–4, where the extra inputs added little accuracy.
2. **Weather and ventilation come next** (ERA5 15.6%, mass balance 9.4%). The top non-history inputs are low-ventilation hours, boundary-layer height and surface pressure, all stagnation-related.
3. **Fire and trajectory inputs get little reliance** (8.0% and 3.6%). Trajectory reliance is higher in Oct–Jan (4.7%), where mean trajectory height is the most-used trajectory input.
4. **Consistency with Stage 4:** reliance does not equal benefit. The model does use the added inputs somewhat, but in Stage 4 they did not reliably improve accuracy.
5. All statements describe model reliance and associations, not causes.

## 5. Not covered
- Trajectory-weighted fire exposure, the four-season scheme and the embargo options are pending. If they change the model, this analysis is rerun.
- Individual cluster-share SHAP values are not interpreted, because cluster labels differ between folds by design.
