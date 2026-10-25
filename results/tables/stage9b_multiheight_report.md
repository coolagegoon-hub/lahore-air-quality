# Stage 9b — Trajectories Arriving at 100 m and 250 m: Results

- **Date:** 2026-10-25
- **Design:** pre-declared in `stage9b_multiheight_predeclaration.md`, approved by the user and committed (`de3fc1d`) before the new trajectories reached the Mac. Nothing was changed after results were seen, and every pre-declared result is reported.
- **Code:** `src/stage9b_multiheight.py` (tests: `tests/test_stage9b_multiheight.py`, 3). **Outputs:** `results/tables/stage9b/`.
- **Input:** `data/raw/hysplit/multiheight/lahore_backtraj_multiheight_endpoints.csv`, from the laptop run of 2026-10-25. HYSPLIT v5.4.2 with the same NCEP/NCAR 2.5° files and settings as the 500 m run, the same `run_trajectories.py` (SHA-256 `f5a3ff46…bb39`); only the height changed.
  - Zip SHA-256 `ef267ac7…53fa` and CSV SHA-256 `67968336…1ebb`, both matching the laptop's report.
- **Input checks:** at 100 m and at 250 m, 2,161 trajectories, all with 73 points, all arriving at 06 UTC, on exactly the 500 m days (none missing, none extra).
- **Comparison set:** all tests use the 1,801 Stage 7 analysis days. PM2.5 is AirNow (U.S. Department of State / EPA AirNow), **preliminary**.
- **Interpretation:** associations only.

## 1. How the trajectories compare across heights

Clusters at 100 m and 250 m are the nearest Stage 7 (500 m) cluster centres. As a check on this method, nearest-centre assignment of the 500 m trajectories themselves agrees with their Ward clusters on 93.7% of analysis days.

| Season | Median 72 h distance, km (100 m / 250 m / 500 m) | Spearman ρ with 500 m (100 m / 250 m) | Days changing cluster vs 500 m, % (100 m / 250 m) | C1 (slow, SE) share, % (100 / 250 / 500 m) |
|---|---|---|---|---|
| Winter | 528 / 564 / 611 | 0.86 / 0.95 | 13.9 / 10.1 | 67 / 63 / 55 |
| Pre-monsoon | 465 / 478 / 527 | 0.85 / 0.95 | 13.5 / 10.4 | 63 / 60 / 50 |
| Monsoon | 398 / 405 / 423 | 0.88 / 0.95 | 9.6 / 7.7 | 85 / 83 / 76 |
| Post-monsoon | 335 / 363 / 426 | 0.88 / 0.95 | 15.6 / 12.7 | 70 / 67 / 55 |

Lower trajectories travelled somewhat shorter distances and were more often in the slow south-easterly cluster. But they were strongly correlated with the 500 m paths: on a 2.5° grid, the three heights mostly follow the same synoptic flow.

## 2. Pathway and stagnation associations

**H1, C2/C1 ratio (95% CI)**

| Season | 100 m raw | 100 m weather-adjusted | 250 m raw | 250 m weather-adjusted | 500 m raw / adjusted (Stage 7) |
|---|---|---|---|---|---|
| Winter | 1.21 (1.02–1.41) | 0.99 (0.82–1.12) | 1.17 (1.02–1.32) | 0.99 (0.85–1.09) | 1.16 / 0.98 |
| Pre-monsoon | 1.34 (1.20–1.53) | 1.12 (1.00–1.25) | 1.33 (1.20–1.51) | 1.11 (1.00–1.25) | 1.30 / 1.07 |
| Monsoon | 1.06 (0.98–1.18) | 0.95 (0.88–1.03) | 1.08 (1.00–1.19) | 0.96 (0.89–1.03) | 1.09 / 0.94 |
| Post-monsoon | 1.14 (0.98–1.40) | 1.02 (0.92–1.24) | 1.14 (0.98–1.39) | 1.05 (0.95–1.25) | 1.07 / 1.04 |

Same pattern as at 500 m: the raw differences largely disappear after weather adjustment. In the pre-monsoon season, the adjusted interval at 100 m and 250 m reaches 1.00 at its lower end.

**H1b, shortest vs longest distance tercile (95% CI)**

| Season | 100 m | 250 m | 500 m (Stage 7) |
|---|---|---|---|
| Winter | 0.90 (0.75–1.03) | 0.88 (0.75–1.01) | 0.86 (0.68–1.03) |
| Pre-monsoon | 0.84 (0.71–0.91) | 0.83 (0.70–0.90) | 0.80 (0.70–0.90) |
| Monsoon | 1.14 (1.02–1.26) | 1.14 (1.02–1.27) | 1.18 (1.05–1.31) |
| Post-monsoon | 0.82 (0.68–1.00) | 0.84 (0.69–1.03) | 0.84 (0.67–1.02) |

**Decoupling criterion (100 m winter, fixed in advance): not supported** (ratio 0.90, which is not above 1). The 250 m result is the same (0.88), and post-monsoon is also below 1 at both heights. Slow trajectories arriving inside ERA5's boundary layer were no more polluted than fast ones. So the 500 m arrival height does not explain why slow air was not more polluted, at least for trajectories computed from 2.5° meteorology.

## 3. Fire exposure (H3, October–November, 296 days)

| Height | c on log(1 + exposure) (95% CI) | Per doubling of (1 + exposure) | Year-shifted nulls ≥ c |
|---|---|---|---|
| 100 m | 0.099 (0.057 to 0.133) | +7.1% | 1 of 9 (shift +2 years: 0.110) |
| 250 m | 0.096 (0.046 to 0.133) | +6.9% | 2 of 9 (+2 years: 0.100; +5 years: 0.101) |
| 500 m (Stage 7) | 0.081 (0.028 to 0.118) | +5.8% | 0 of 9 |

- At the lower heights, the fire coefficient is slightly larger and its interval excludes zero.
- However, the real record no longer beats every year-shifted record. So H3's third criterion (c above 95% of the null coefficients) **fails at 100 m and 250 m**.
- Year-shifted coefficients range from 0.005 to 0.110, so much of the fire–PM2.5 link at these heights can be reproduced by fires at the right time of season in other years.
- The H3 result at 500 m should therefore be read as sensitive to arrival height.

## 4. Forecasting with trajectory features from each height (zero embargo, 138 common weeks)

| Height | MAE of RF 5 (RF 4 = 28.7) | RF 5 − RF 4 (95% CI) | RF 1 + traj − RF 1 (95% CI) |
|---|---|---|---|
| 100 m | 28.3 | −0.4 (−1.4 to +0.7) | −0.8 (−2.4 to +1.0) |
| 250 m | 28.4 | −0.3 (−1.3 to +0.9) | −1.1 (−3.0 to +0.8) |
| 500 m (Stage 4) | 28.3 | −0.4 (−1.3 to +0.8) | −1.1 (−2.8 to +0.6) |

- Oct–Jan, RF 5 − RF 4: −0.5 (−2.7 to +1.7) at 100 m and −0.4 (−2.8 to +2.0) at 250 m.
- The trajectory layer gives no reliable gain at any height.

## 5. Not done (as declared)

Other arrival times, other meteorology (GDAS or ERA5) and CWT maps at the new heights. All three heights use the same 2.5° meteorology, so this stage does not address the resolution concern.
