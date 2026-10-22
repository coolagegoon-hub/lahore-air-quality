# Stage 4 — Pre-declared Design: HYSPLIT Trajectory Features (Model Layer 5)

- **Declared:** 2026-10-23, before any trajectory feature or model was computed.
- **Input:** `data/raw/hysplit/lahore_backtraj_endpoints.csv` (SHA-256 `52bd34cf…82a8`, verified to match the README).
  - 2,161 daily 72 h back-trajectories, arriving at 06:00 UTC (11:00 PKT) at 500 m AGL at 31.560078 N, 74.33589 E.
  - Produced with HYSPLIT v5.4.2 and NCEP/NCAR Reanalysis 2.5° meteorology; no failed days.
- **Validation on this machine:** 73 points per trajectory (hours 0–72); every day present; no gaps or duplicates.
- **Scope:** this is a new model layer. Earlier results are unchanged and reported alongside it.

## Unchanged from Stage 3
- Target: eligible weekly mean PM2.5 (≥ 6/7 days), AirNow series (preliminary).
- Cutoff: Monday 00:00 PKT. Walk-forward with an expanding window, refitted for every target week, ≥ 52 training weeks.
- Random Forest: 300 trees, min_samples_leaf 5, max_features 0.33, seed 20261021.
- Layers L1–L4 and their features.
- Common-set scoring (all / Oct–Jan / other), moving-block bootstrap with seed 20261021.
- Zero embargo, as in Stage 3. The paper's embargo options (one week; per-source latency) are not yet implemented and are pending.
- Season split for reporting: the Oct–Jan definition used in Stages 2–3, kept for comparability. The paper's four-season scheme is pending.

## Trajectory handling
1. **Day assignment:** each trajectory belongs to the PKT calendar date of its arrival (06 UTC = 11:00 PKT).
2. **Features for target week T use only the 7 trajectories arriving on the PKT days of week T−1**, all before T's cutoff. No trajectory arriving in week T or later is used.
3. **Shape vector for clustering:** positions at hours back 6, 12, …, 72 (12 points), converted to km east and north of the receptor (equirectangular: x = R·cos φ₀·Δλ, y = R·Δφ, with R = 6371.0088 km). This gives 24 numbers in a common unit, so no scaler is fitted.
4. **In-fold clustering (no leakage):**
   - For each target week T, k-means is fitted ONLY on trajectories arriving before T − 7 days, i.e. those that can enter training-row features (training targets end before T, so their features come from week T−2 or earlier).
   - Settings: k = 6, n_init = 20, random_state = 20261021. At least 365 trajectories are required; otherwise no forecast is made.
   - The trajectories of week T−1 (the test row's features) are only **assigned** to the nearest fitted centre.
   - Training-row features in that fold use the same fold's clustering, so cluster labels are consistent within each fold. Labels may differ between folds; this does not affect predictions. Any descriptive pathway analysis will use a separate single clustering of all trajectories and is not part of the forecast evaluation.
5. **Weekly trajectory features (from week T−1):**

   | Feature | Definition |
   |---|---|
   | `traj_frac_c1 … c6` | Share of the week's trajectories assigned to each cluster (fold-specific) |
   | `traj_mean_dist72_km` | Mean great-circle distance from Lahore of the 72 h endpoint (transport distance) |
   | `traj_frac_pts_east_se` | Share of hourly endpoints (hours 1–72) within 500 km at bearing 45°–180° (same sector as the FIRMS features) |
   | `traj_mean_height_m` | Mean endpoint height AGL over hours 1–72 |

   **Completeness:** features are NaN if fewer than 6 of the 7 trajectories exist (none are missing in this dataset). No imputation.

## Models
- **L5_plus_traj:** L4 features + the 9 trajectory features (cluster shares and the 3 continuous features). **Primary.**
- **L1_plus_traj:** L1 (PM2.5 history) + the 9 trajectory features. Secondary; isolates trajectory information without the other inputs.

## Comparisons to report (all of them, whatever the outcome)
1. **Primary:** L5 vs L4, ΔMAE with a 95% block-bootstrap CI using 4-week blocks, all weeks and Oct–Jan.
2. **Block-length checks:** the same comparison with 2- and 8-week blocks.
3. L1_plus_traj vs L1.
4. L5 vs the Ridge PM2.5-history model, climatology and persistence.
5. **k sensitivity (secondary):** L5 with k = 4 and k = 8, MAE only.
6. **Also reported:** MAE, RMSE, R², bias and skill vs persistence (1 − MAE/MAE_persistence) for every method on the common set.

## Interpretation rules
- These are predictive comparisons only. Cluster shares are associations, not source attribution.
- Several comparisons are run, so a single CI excluding 0 is weak evidence.
- Not yet included (pending): trajectory-weighted fire exposure, the H1–H3 association tests, the four-season scheme, embargo options and SHAP.
