# Stage 4 — HYSPLIT Trajectory Features (Model Layer 5): Results

- **Date:** 2026-10-23
- **Design:** pre-declared in `stage4_predeclaration.md`, committed (2a4b644) before any fitting. Everything below follows that declaration; no setting was changed after seeing results.
- **Code:** `src/trajectory_features.py`, `src/stage4_trajectory_model.py`; tests `tests/test_trajectory_features.py` (5).
- **Outputs:** `results/tables/stage4/`.
- **Data:**
  - HYSPLIT v5.4.2 back-trajectories (72 h, 06 UTC arrival, 500 m AGL) driven by NCEP/NCAR Reanalysis 2.5° meteorology. That grid is coarse, so these are synoptic-scale transport descriptors.
  - PM2.5 is AirNow, U.S. Department of State / EPA AirNow; the data are **preliminary**.
- **Settings:** zero embargo, as in Stages 2–3. Season split for reporting is Oct–Jan (the four-season scheme is pending).

## 1. Trajectory data check (this machine)

| Check | Result |
|---|---|
| Trajectories | 2,161, one per day from 2019-04-01 to 2025-02-28 |
| Points | 73 per trajectory (hours 0–72); no gaps or duplicates |
| Arrival | 06 UTC, 500 m, all starting at 31.56 N, 74.336 E |
| File checksum | matches the README |
| Failed days | none |
| Forecast-week coverage | every forecast week has all 7 trajectories from the previous week |

**Descriptors (per trajectory):**
- 72 h start-point distance from Lahore: median 481 km (IQR 224–980).
- Share of hourly points in the east/south-east sector within 500 km: mean 0.47.
- Mean height over the 72 h: median 1,544 m AGL.

## 2. Forecast results on the common set

The common set is the same 133 eligible weeks as Stage 3 (2021-05-17 → 2025-02-10), of which 52 are Oct–Jan. Error is prediction − observed, in µg/m³.

| Method | MAE | RMSE | R² | Bias | Skill vs persistence |
|---|---|---|---|---|---|
| Persistence | 36.41 | 57.91 | 0.638 | +0.37 | 0.000 |
| Climatology | 33.67 | 50.25 | 0.728 | −11.59 | 0.075 |
| Ridge PM2.5-history | 30.52 | 47.09 | 0.761 | −4.82 | 0.162 |
| RF L1 (history) | 30.17 | 48.61 | 0.745 | −9.17 | 0.171 |
| RF L4 (+ ERA5, fire, mass balance) | 29.27 | 48.69 | 0.744 | −7.55 | 0.196 |
| **RF L5 (L4 + trajectories), primary** | **29.07** | 48.13 | 0.750 | −6.38 | 0.201 |
| RF L1 + trajectories | 28.87 | 47.07 | 0.761 | −7.29 | 0.207 |
| RF L5, k = 4 (sensitivity) | 29.49 | 48.53 | 0.746 | −7.00 | 0.190 |
| RF L5, k = 8 (sensitivity) | 28.90 | 48.07 | 0.751 | −6.64 | 0.206 |

**Oct–Jan (52 weeks), MAE:** persistence 64.87; climatology 55.83; Ridge history 56.09; RF L4 51.05; RF L5 50.78; RF L1 + trajectories 51.06.

**Other months (81 weeks), MAE:** Ridge history 14.10; RF L4 15.29; RF L5 15.14; RF L1 + trajectories 14.62.

## 3. Pre-declared comparisons (ΔMAE, 95% moving-block bootstrap CI; negative = first model better)

| Comparison | Block | All weeks (n = 133) | Oct–Jan (n = 52) |
|---|---|---|---|
| **L5 vs L4 (primary)** | 4 wk | −0.20 (−1.22, +0.98) | −0.27 (−2.67, +2.55) |
| L5 vs L4 | 2 wk | −0.20 (−1.20, +0.90) | −0.27 (−2.76, +2.44) |
| L5 vs L4 | 8 wk | −0.20 (−1.07, +0.99) | −0.27 (−2.79, +2.43) |
| L1 + trajectories vs L1 | 4 wk | −1.30 (−3.28, +0.67) | −2.11 (−5.76, +2.62) |
| L5 vs Ridge PM2.5-history | 4 wk | −1.44 (−6.02, +1.74) | −5.30 (−13.67, +2.73) |
| L5 vs climatology | 4 wk | **−4.60 (−8.87, −1.53)** | −5.05 (−11.58, +1.23) |
| L5 vs persistence | 4 wk | **−7.33 (−13.02, −2.38)** | **−14.08 (−25.27, −3.62)** |

## 4. Reading

1. **Primary result: adding trajectory features to the full model (L5 vs L4) gives no reliable improvement.** MAE falls by 0.2 µg/m³ overall and 0.3 in Oct–Jan, and the 95% CIs comfortably include zero. The conclusion is the same with 2-, 4- and 8-week bootstrap blocks.
2. **Trajectories added to PM2.5 history alone** (L1 + trajectories vs L1) lower MAE by 1.3 µg/m³ overall. 90% of bootstrap resamples favour them, but the CI still includes zero (−3.3, +0.7). So this is inconclusive, but more suggestive than the L5 result. In the full model, much of this information may already be carried by the ERA5 wind and ventilation features.
3. **The choice of cluster count barely matters:** k = 4, 6 and 8 give MAE 29.5, 29.1 and 28.9.
4. **The pattern from Stage 3 is unchanged:**
   - the trajectory-augmented model beats persistence (overall and Oct–Jan) and climatology (overall);
   - it does not reliably beat the Ridge PM2.5-history model;
   - it still under-predicts high smog-season weeks (bias about −25 in Oct–Jan).
5. **Interpretation limits:** these are predictive comparisons with zero embargo. Cluster shares are associations with air-mass pathways, not source attribution. Several comparisons were run, so the few CIs that exclude zero should be read cautiously.

## 5. Still pending (not done here)
- Trajectory-weighted fire exposure.
- The H1–H3 association tests.
- The four-season scheme.
- The embargo options (one week; per-source latency).
- A single descriptive clustering of all trajectories for the pathway maps.
- SHAP by feature group.
- Results figures.
