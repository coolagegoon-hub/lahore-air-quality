# Stage 9c — Report: GDAS 1° vs NCEP/NCAR 2.5° trajectories, one year

- **Run:** 2026-10-27, `python -m src.stage9c_gdas_comparison`, under the pre-declared design in
  `stage9c_gdas_predeclaration.md` (approved 2026-10-25, before any GDAS file existed).
- **Outputs:** `results/tables/stage9c/` (`trajectory_agreement.csv`, `estimates_ncep_vs_gdas.csv`,
  `estimates_check_ncep_nearest_centre.csv`, `stage9c_summary.json`).
- **Tests:** `tests/test_stage9c_gdas_comparison.py` (4, synthetic data); the full suite passes (151).

## Inputs

- **GDAS 1° endpoints:** `data/raw/hysplit/hysplit_gdas1_out/lahore_backtraj_gdas1_endpoints.csv`, SHA-256 `46b1cd04…8ef7`.
  - 1,095 trajectories (365 days × 100, 250 and 500 m);
  - 73 points each, all arriving at 06 UTC, with no empty values.
- **Met files:** 61 GDAS files, all matching NOAA's MD5 (`manifest.csv`, SHA-256 `b937816f…e4cf`).
- **NCEP comparison set:** the existing 2.5° trajectories for the same 365 days, at 500 m (main file) and at 100/250 m (Stage 9b file).
- **Integrity check before interpreting:**
  - both sets start at the identical receptor point;
  - their endpoint times match row by row;
  - the differences below are therefore between the two meteorologies, not a joining error.

## Choices fixed in the code before running

These points were not spelled out in the pre-declaration, so they were fixed in the code first (see its docstring):

- **Cluster agreement (rule a):** both sources are assigned to the nearest Stage 7 centre, so all 365 days use the same rule.
- **NCEP estimates:** use the published Stage 7 labels and fire exposure.
- **GDAS estimates:** use nearest-centre labels and GDAS fire exposure.
- **Check:** the NCEP estimates are repeated with nearest-centre labels.
- **H1:** the raw C2/C1 ratio of geometric means.
- **Random seed:** every estimate uses a fresh seed 20261025, so both sources draw the same bootstrap blocks.

## 1. Trajectory agreement (500 m unless stated)

| | All 365 days | Winter (90) | Post-monsoon (61) |
|---|---|---|---|
| Same cluster (%) | **69.6** | 72.2 | 50.8 |
| Spearman, 72 h distance | **0.22** | 0.33 | 0.22 |
| Median 72 h distance, GDAS / NCEP (km) | 693 / 600 | 481 / 607 | 264 / 681 |
| Mean endpoint height, GDAS / NCEP (m) | 1,215 / 1,817 | 1,387 / 1,546 | 862 / 2,414 |
| Separation at 24 h, median (IQR), km | 254 (157–363) | 289 (206–371) | 157 (97–275) |
| Separation at 48 h, median (IQR), km | 432 (255–754) | 415 (246–633) | 278 (192–603) |
| Separation at 72 h, median (IQR), km | 713 (385–1,334) | 586 (382–884) | 783 (348–1,441) |
| Separation at 72 h as share of NCEP distance (median) | 1.06 | 0.78 | 0.96 |

**Lower heights:**
- At 100 m and 250 m, agreement is as low or lower: same cluster 65% and 70%; Spearman 0.15 for both.
- The GDAS trajectories stay much lower and, in the post-monsoon season and winter, travel much shorter distances than the NCEP ones.
- At 100 m, the mean height is 594 m with GDAS against 1,387 m with NCEP.

**Separations:**
- Typical separations are about as large as the NCEP transport distance itself.
- Only about 7 of 10 days fall in the same cluster.

**Reading:** the 2.5° and 1° meteorologies give materially different 72 h paths for this receptor. The GDAS paths are lower and, in winter and post-monsoon, shorter. One plausible contributor is that the reanalysis files lack surface flux fields (the 2.5° runs printed the `FLUXES not found / KBLS=2` notice; GDAS did not). This was not tested, and it is a possible explanation, not a finding.

## 2. The five pre-declared estimates (year's analysis days, 500 m)

| Estimate | NCEP 2.5° (95% CI) | GDAS 1° (95% CI) | GDAS outside NCEP CI | Opposite sides of no-effect value |
|---|---|---|---|---|
| H1 C2/C1, winter | 1.07 (0.80–1.40) | 0.82 (0.70–1.03) | no | **yes** |
| H1 C2/C1, post-monsoon | 1.17 (0.72–2.13) | 0.93 (0.62–1.19) | no | **yes** |
| H1b shortest/longest, winter | 0.94 (0.73–1.26) | **1.35 (1.04–1.53)** | **yes** | **yes** |
| H1b shortest/longest, post-monsoon | 0.82 (0.46–1.39) | 0.93 (0.76–1.29) | no | no |
| H3 fire coefficient c, Oct–Nov 2024 | 0.144 (−0.071–0.218) | 0.133 (−0.101–0.188) | no | no |

**Check with NCEP nearest-centre labels** (`estimates_check_ncep_nearest_centre.csv`):
- The same three estimates trigger.
- In addition, the GDAS winter C2/C1 ratio lies outside the NCEP interval (NCEP 1.08, 0.83–1.39).

**Notes:**
- With one year, all intervals are wide.
- The two H1 sign flips are between estimates whose intervals both include 1.
- The winter H1b change is the clearest:
  - With NCEP, the year shows no stagnation pattern.
  - With GDAS, days with the shortest 72 h paths have about 35% higher geometric mean PM2.5 than days with the longest paths, and the interval excludes 1.
  - This is an association in one winter, not evidence of cause.
- The fire coefficient is essentially unchanged (0.13 vs 0.14).

## 3. Decision rule (pre-declared)

| Condition | Result | Holds? |
|---|---|---|
| (a) Same cluster < 80% of days | 69.6% | **yes** |
| (b) Spearman of 72 h distance < 0.8 | 0.22 | **yes** |
| (c) Any estimate outside the NCEP CI or on the opposite side of no effect | 3 of 5 | **yes** |

**Verdict: the sharper meteorology changes the results substantially.**

As pre-declared:
- The paper reports the difference.
- The user decides between:
  1. **Recomputing the whole record with GDAS 1°**, about 180 GB, as a new pre-declared stage, and redoing the trajectory analyses with it.
  2. **Dropping the trajectory-based claims that depend on the resolution.**

The fire-exposure association (H3) did not move in this year, and nothing in the forecasting results depends on this comparison beyond the trajectory layer.
