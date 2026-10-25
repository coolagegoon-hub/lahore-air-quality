# Stage 7 — Air-Mass Pathway Association Analysis (H1–H3): Results

- **Date:** 2026-10-25
- **Design:** pre-declared in `stage7_association_predeclaration.md`, approved by the user and committed (`57f17be`) before any analysis code was run. Nothing was changed after results were seen. All pre-declared results are reported below.
- **Code:** `src/association_analysis.py` (tests: `tests/test_association_analysis.py`, 9), figures `src/figures_association.py`. Outputs: `results/tables/stage7/`; figures `results/figures/fig10`–`fig14`.
- **Data:** PM2.5 is AirNow (U.S. Department of State / EPA AirNow), **preliminary**; Stage 6 record. Trajectories: HYSPLIT v5.4.2, NCEP/NCAR 2.5°, 72 h, 06:00 UTC, 500 m AGL. ERA5 at 31.50° N, 74.25° E. FIRMS VIIRS Suomi NPP.
- **Interpretation:** associations only. Nothing here attributes PM2.5 to sources or shows causes.

## 1. Analysis days

1,801 PKT days with a complete daily PM2.5 mean and a trajectory: winter 475, pre-monsoon 385, monsoon 633, post-monsoon 308. Fire exposure is missing on 22 days, because 10 dates had no Suomi NPP detections within 500 km while NOAA-20 had ≥ 100 (including 2 Nov 2023 and 4–6 Nov 2024).

## 2. Descriptive clustering (all 2,161 trajectories)

| k | Δ(k), % | silhouette |
|---|---|---|
| 2 | 70.6 | 0.417 |
| **3** | **38.8** | **0.419** |
| 4 | 23.5 | 0.357 |
| 5–10 | 9–16 | 0.27–0.29 |

The rule (largest k with Δ(k) ≥ 30%) gives **k = 3**. Agreement with k-means at k = 3: adjusted Rand index 0.82.

| Cluster | Share | Mean 72-h distance | Mean height | Months most common |
|---|---|---|---|---|
| C1: slow, from SE | 60% (1,300) | 375 km | 1,064 m | July–September (77–90% of days); about half of days in other months |
| C2: fast, from NW | 37% (802) | 1,171 km | 2,295 m | about half of days in April–June and October–December |
| C3: fast, from W | 3% (59) | 3,632 km | 3,298 m | mainly February–March (7–10%) |

## 3. H1 — PM2.5 by cluster within seasons

Median daily PM2.5 (µg/m³): winter C1 186, C2 231, C3 170; pre-monsoon 61, 84, 104 (C3 n = 8); monsoon 54, 57; post-monsoon 146, 160, 158 (C3 n = 8). C3 has fewer than 30 days in every season (at most 24, in winter), so it is described but not tested.

Ratio of geometric means, C2 vs C1 (95% block-bootstrap CI), and block-permutation p (Holm-adjusted across the four seasons):

| Season | Ratio C2/C1 | p (Holm) |
|---|---|---|
| Winter | 1.16 (1.00–1.28) | 0.071 (0.21) |
| Pre-monsoon | **1.30 (1.18–1.49)** | **0.001 (0.006)** |
| Monsoon | 1.09 (1.00–1.19) | 0.085 (0.21) |
| Post-monsoon | 1.07 (0.91–1.34) | 0.52 (0.52) |
| Oct–Jan (secondary) | 1.14 (1.04–1.30) | 0.056 |

**Confounding ladder (C2/C1):**

| Season | (a) raw | (b) anomaly from day-of-year climatology | (c) adjusted for ventilation, wind, temperature, humidity, rain |
|---|---|---|---|
| Winter | 1.16 (1.00–1.28) | 1.15 (1.02–1.26) | 0.98 (0.85–1.09) |
| Pre-monsoon | 1.30 (1.17–1.49) | 1.36 (1.21–1.55) | 1.07 (0.96–1.22) |
| Monsoon | 1.09 (1.00–1.18) | 0.98 (0.90–1.07) | 0.94 (0.87–1.00) |
| Post-monsoon | 1.07 (0.92–1.36) | 1.03 (0.92–1.24) | 1.04 (0.92–1.26) |

**Sensitivity:** the same pattern at k = 2 and k = 4 (e.g. pre-monsoon fast/slow ratios 1.28–1.33) and with 14- and 28-day blocks.

**Reading:** pathways differ modestly in PM2.5 within seasons, most clearly in the pre-monsoon season, where fast north-westerly days average about 30% higher than slow south-easterly days. Once weather is accounted for, every ratio moves to about 1 with intervals including 1: the pathway differences largely go with the weather that accompanies each pathway. **H1 is supported only for raw differences in the pre-monsoon season** (and weakly in winter and the monsoon), **not after weather adjustment.**

## 4. H1b — stagnation by transport distance (secondary)

Ratio of geometric means, shortest vs longest distance tercile: winter 0.86 (0.68–1.03); pre-monsoon 0.80 (0.70–0.90); monsoon 1.18 (1.05–1.31); post-monsoon 0.84 (0.67–1.02). **Not supported**: except in the monsoon, slow (short-distance) trajectory days were not more polluted, and in the pre-monsoon they were less polluted. Trajectory distance at 500 m on a 2.5° grid does not appear to measure the surface stagnation that matters for PM2.5 (see H2).

## 5. H2 — ventilation

Slope b of log PM2.5 on log ventilation coefficient (95% CI); model 2 adds cluster:

| Season | Model 1 | Model 2 |
|---|---|---|
| Winter | −0.47 (−0.55 to −0.39) | **−0.47 (−0.57 to −0.39)** |
| Pre-monsoon | −0.14 (−0.21 to +0.00) | −0.16 (−0.24 to −0.02) |
| Monsoon | −0.06 (−0.19 to +0.04) | −0.07 (−0.19 to +0.03) |
| Post-monsoon | −0.48 (−0.61 to −0.38) | **−0.47 (−0.61 to −0.37)** |

**H2 is supported in winter, post-monsoon and pre-monsoon, not in the monsoon.** In winter and October–November, a 10% lower ventilation coefficient goes with about 5% higher PM2.5, regardless of pathway. The slopes (about −0.5) are well short of the −1 expected if PM2.5 scaled simply with 1/ventilation, so emissions, inflow or removal also vary.

## 6. H3 — fire exposure, October–November

Model on 296 October–November days with exposure available: log PM2.5 ~ log VC + cluster + day of year + year + c·log(1 + FE).

| Exposure definition | c (95% CI) |
|---|---|
| **Primary: 50 km, endpoints ≤ 1,500 m** | **0.081 (0.028 to 0.118)** |
| 25 km | 0.045 (−0.000 to 0.079) |
| 100 km | 0.131 (0.057 to 0.194) |
| No height filter | 0.092 (0.046 to 0.128) |
| Primary, 14-day blocks | 0.081 (0.018 to 0.118) |
| Primary, 28-day blocks | 0.081 (0.031 to 0.116) |

Year-shifted fire records (9 shifts with enough data): c from 0.011 to 0.071; **none** reaches the real 0.081 (share ≥ c = 0).

**H3 is supported:** more trajectory-weighted fire exposure goes with higher October–November PM2.5 after accounting for ventilation, pathway, time of season and year, and the real fire record beats every year-shifted record. The size is modest: doubling (1 + FE) goes with about 6% higher PM2.5. The null coefficients are themselves positive, so part of any raw fire–PM2.5 link reflects seasonal timing; the 25 km version is borderline.

## 7. CWT maps (descriptive)

Endpoint density peaks near Lahore in both seasons. In the post-monsoon season, the highest weighted CWT values lie in cells south-east of Lahore (about 29–30° N, 77–79° E) and north-west of it (about 32–33° N, 70–71° E); in winter, high values cover a broad area around and north-west of Lahore. With 2.5° meteorology and the trail effect, single cells are not interpreted, and the maps show where air passed before polluted days, not where pollution came from.

## 8. Not done (as declared)

Other arrival heights, arrival times and meteorology (no such trajectories); the same-day "explanatory model" (deferred).
