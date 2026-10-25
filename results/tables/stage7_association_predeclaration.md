# Stage 7 — Pre-declared Design: Air-Mass Pathway Association Analysis (H1–H3)

- **Declared:** 2026-10-25, before any pathway, cluster, fire-exposure or association result was computed.
- **Status:** approved by the user on 2026-10-25 ("I approve the Stage 7 plan. Commit it and run the analysis."). Committed before any analysis code was run.
- **Purpose:** answer parts 1 and 2 of the research question: which incoming air-mass pathways and weather conditions go with high PM2.5 in Lahore, and how much of that is linked to ventilation and upwind fire activity. This is an **association** analysis. It does not forecast and it does not attribute sources or causes.
- **Data:** the Stage 6 record (AirNow, preliminary; credit the U.S. Department of State and the EPA AirNow program); the 2,161 HYSPLIT trajectories (v5.4.2, NCEP/NCAR 2.5°, 72 h, 06:00 UTC, 500 m AGL); ERA5 at 31.50° N, 74.25° E; FIRMS VIIRS Suomi NPP standard processing.
- **Separate from forecasting:** nothing here changes the forecast models or their results. The descriptive clustering below uses all trajectories at once, which is allowed only because it is not used for forecasting (CLAUDE.md).

## 1. Unit of analysis and outcome

- **Unit:** one PKT calendar day with a complete daily PM2.5 mean (≥ 18 of 24 valid hours, after the 7-hour repeated-value rule) **and** a trajectory arriving that day.
- **Matching:** each trajectory arrives at 06:00 UTC = 11:00 PKT on day d and is matched to the PKT daily mean of day d (about 11 hours before arrival and 13 after). This is stated in the methods.
- **Outcome:** log daily mean PM2.5 (natural log). Effects are reported as ratios of geometric means (e.g. "1.25 = 25% higher").
- **Seasons (primary):** winter (December–February), pre-monsoon (March–May), monsoon (June–September), post-monsoon (October–November), by PKT date. October–January is reported as a secondary split, for comparability with the forecasts.

## 2. Pathway variables (per day)

1. **Cluster** (Section 3).
2. **Transport distance:** great-circle distance from Lahore of the 72-hour endpoint (km). Short distance = slow, stagnant air.
3. **Stagnation tercile:** tercile of transport distance, computed within each season over the analysis days.
4. **East/south-east share:** share of hourly endpoints (hours 1–72) within 500 km at bearing 45°–180° (same sector as the fire features).
5. **Mean endpoint height** above ground (hours 1–72).

## 3. Descriptive clustering (all 2,161 trajectories, fitted once)

- **Shape vector:** positions 6, 12, …, 72 hours back, in km east and north of the receptor (equirectangular, R = 6371.0088 km); 24 numbers, no scaling (as in Stage 4).
- **Method:** Ward agglomerative clustering (Euclidean), which merges the pair of clusters that least increases total within-cluster variance (TSV), the same principle as HYSPLIT's own clustering.
- **Choosing k (fixed rule):** compute TSV for k = 2 … 10. For each k, Δ(k) = 100 × [TSV(k−1) − TSV(k)] / TSV(k). Choose the **largest k with Δ(k) ≥ 30%** (HYSPLIT User's Guide rule of thumb: stop just before a large jump). If no k reaches 30%, choose the k with the largest Δ(k). Also report the silhouette score for k = 2 … 10.
- **Robustness:** repeat the cluster comparisons at k − 1 and k + 1. As a consistency check, report the agreement (adjusted Rand index) with k-means at the chosen k (seed 20261021).
- **Description:** mean path of each cluster, its frequency overall and by month and season, mean transport distance and mean height. Clusters are named after their mean path and speed (e.g. "slow, local", "fast north-westerly"), never after assumed sources or countries.

## 4. Weather (per PKT day, ERA5)

Mean 10 m wind speed; mean boundary-layer height (BLH); mean ventilation coefficient VC = mean of hourly BLH × 10 m wind speed (m² s⁻¹); mean 2 m temperature; mean relative humidity; total precipitation, with a rain day = ≥ 1 mm. Same unit conversions and PKT day assignment as `src.era5_features` and `src.mass_balance_features`.

## 5. Trajectory-weighted fire exposure (per day)

- **Detections:** VIIRS Suomi NPP standard processing, presumed vegetation fires, nominal or high confidence (as in `src.firms_features`).
- **Interception:** a detection is intercepted if it lies within **50 km** (great-circle) of any hourly endpoint at hours 1–72 whose height is **≤ 1,500 m AGL**, and its PKT detection date is the endpoint's PKT date or the day before.
- **Exposure:** FE = total fire radiative power (MW) of the **unique** detections intercepted by the day's trajectory (each detection counted once). Analysed as log(1 + FE).
- **Missing satellite days:** a day is treated as missing for fire exposure (not zero) if Suomi NPP has no detections within 500 km while NOAA-20 has ≥ 100 that day (for example, the reported Suomi NPP processing gap in early November 2024).
- **Null comparison:** recompute FE with the fire record shifted by whole years (±1 to ±5 years, where data exist), which keeps each fire's place and time of season but breaks its link with the actual trajectory.
- This indicator is the project's own construction, following the trajectory–fire interception idea used in the literature. It measures detected fire activity near the probable path of incoming air, not smoke delivered to Lahore.

## 6. Hypotheses and tests

**Uncertainty, all tests:** moving-block bootstrap over days, with blocks of **7 consecutive days** resampled within each season-year (14- and 28-day blocks as checks), 2,000 resamples, seed 20261025. Where a p-value is given, it comes from a **block permutation** test: cluster labels (or the variable of interest) are shuffled in 7-day blocks within each season-year, 2,000 permutations. With several tests, results are judged by effect sizes and intervals, and Holm's correction is applied across the four seasons.

| ID | Hypothesis (association) | Test | Counts against it |
|---|---|---|---|
| **H1** | Within a season, daily PM2.5 differs between trajectory clusters. | Per season: regression of log PM2.5 on cluster; ratios of geometric means relative to the season's most frequent cluster, with bootstrap CIs; global block-permutation test (statistic: between-cluster variance of log PM2.5). Season–cluster cells with < 30 days are described but not tested. | No difference between clusters within seasons, or differences that vanish at k − 1 and k + 1. |
| **H1b** (secondary) | Within a season, days in the shortest-distance (most stagnant) tercile have higher PM2.5 than days in the longest tercile. | Ratio of geometric means, shortest vs longest tercile, per season, with bootstrap CI. | Interval includes 1, or the ratio is below 1. |
| **H2** | Within a season, high-PM2.5 days go with lower ventilation, whatever the pathway. | Per season: log PM2.5 = a + b·log VC (model 1), then adding cluster indicators (model 2). Report b with bootstrap CI in both models. b near −1 is the box-model consistency check (Section 5.5 of the paper). | b not negative, or its interval includes 0 in model 2. |
| **H3** | In October–November, days with more trajectory-weighted fire exposure have higher PM2.5 after accounting for ventilation, pathway, seasonal timing and year, and the real fire record beats year-shifted records. | October–November days: log PM2.5 = log VC + cluster + day-of-year (linear) + year indicators + c·log(1 + FE). Report c with bootstrap CI and the share of year-shifted null coefficients ≥ c. | c not positive, its interval includes 0, or c is not above 95% of the null coefficients. |

**Confounding ladder (reported for H1 in every season, whatever the outcome):** cluster effects (a) raw; (b) on anomalies from a day-of-year climatology (each day's log PM2.5 minus the mean log PM2.5 of all days within ±15 calendar days, across years); (c) adjusted for log VC, wind speed, temperature, relative humidity and rain day. Shrinkage from (a) to (c) shows how much of a pathway difference goes with the weather that accompanies it. Note in the paper: BLH and ventilation are partly affected by aerosol itself, so (c) may over-adjust.

## 7. Maps (descriptive)

- **Concentration-weighted trajectory (CWT) maps:** 1° grid (the 2.5° meteorology cannot support finer detail); each cell gets the mean daily PM2.5 of the days whose hourly endpoints (hours 1–72) fall in it; low-count weights 1 / 0.7 / 0.42 / 0.05 for cells with > 80 / 20–80 / 10–20 / < 10 endpoints (openair's default scheme). Separate maps for post-monsoon and winter, each beside a trajectory-frequency map. Single cells are not interpreted.

## 8. Sensitivity (only these)

k − 1 and k + 1; 14- and 28-day bootstrap blocks; fire buffer 25 and 100 km; no height filter for fire exposure; the October–January season split.
**Not possible with the existing trajectories** (stated as limitations): other arrival heights, other arrival times, other meteorology.

## 9. Outputs and reporting

- Code: `src/association_analysis.py`, with synthetic-data tests in `tests/test_association_analysis.py`. Outputs: `results/tables/stage7/`. Report: `results/tables/stage7_association_report.md`.
- Figures: cluster mean paths (with Natural Earth borders and frequencies); PM2.5 by cluster and season (box plots with n); PM2.5 against transport distance by season (binned); fire exposure against PM2.5 anomaly, October–November; CWT and frequency maps.
- **Every result above is reported, whatever it shows.** No threshold, k rule, buffer or season split is changed after results are seen.
- **Deferred (not part of Stage 7):** the "explanatory model" (same-day Random Forest with SHAP) described in Section 5.14 of the paper draft. The paper will say so.
