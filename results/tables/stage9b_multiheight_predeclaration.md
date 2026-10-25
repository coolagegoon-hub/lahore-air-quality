# Stage 9b — Pre-declared Design: Do the Results Change at Lower Trajectory Arrival Heights (100 m and 250 m)?

- **Declared:** 2026-10-25, **before the 100 m and 250 m trajectories exist**. They are being computed on the processing laptop (`data/raw/hysplit/LAPTOP_RUN_multiheight.md`).
- **Status:** approved by the user on 2026-10-25 ("I approve the Stage 9b plan. Commit it now, and push it together with the Stage 9a commit (not the paper)."). Committed before the new trajectory file reached the Mac.
- **Why:** Stage 9a found that at the 06 UTC arrival time, ERA5's boundary layer was below 500 m on 78% of winter days (92% of the most polluted third). The 500 m trajectories may therefore describe air above the surface smog layer. If so, trajectories arriving inside that layer (100 m, and on most winter days 250 m) could show what 500 m missed. The clearest case is that slow 500 m air was *not* more polluted (H1b not supported).
- **Scope:** nothing in Stages 1–9a changes. The 500 m results remain the primary results; the lower heights are a declared sensitivity analysis. Every result below is reported, whatever it shows.

## 0. Input checks (before any analysis)

- **File:** `lahore_backtraj_multiheight_endpoints.csv` from the laptop.
- **Required:**
  - exactly 4,322 trajectories (2,161 days × 100 m and 250 m), all arriving at 06 UTC;
  - 73 points each (hours 0–72);
  - the same days as the 500 m set;
  - the SHA-256 matches the laptop's report.
- **If the checks fail:** any failed or short trajectory is listed and its day is dropped for that height only. If more than 1% of days fail at a height, that height is reported as incomplete and the user is asked before going on.
- **Provenance:** recorded as for the 500 m set (HYSPLIT v5.4.2, NCEP/NCAR 2.5°, 72 h, met vertical velocity).
- **Same days everywhere:** the 1,801 Stage 7 analysis days (complete daily PM2.5 mean and a trajectory) are used at every height, so heights are compared on the same days.

## 1. How the trajectories compare across heights (descriptive)

Per season (winter, pre-monsoon, monsoon, post-monsoon), at 100, 250 and 500 m:
- median and interquartile range of the 72 h transport distance;
- Spearman correlation of daily transport distance between heights;
- the share of days assigned to each Stage 7 pathway cluster. Each 100 m and 250 m trajectory is assigned to the **nearest Stage 7 cluster centre** (k = 3, fitted on the 500 m trajectories), so clusters mean the same thing at every height. The share of days whose cluster changes from 500 m is also reported.

## 2. Pathway and stagnation associations at each height (same methods as Stage 7)

All tests use log daily PM2.5 within seasons, effects as ratios of geometric means, and a moving-block bootstrap of 7-day blocks within season-years (2,000 resamples, seed 20261025).

- **H1 at 100 and 250 m:** ratio of geometric means between the two main clusters (C2/C1, nearest-centre assignment), raw and adjusted for weather (ventilation, wind, temperature, humidity, rain), per season. Cells with fewer than 30 days are described, not tested.
- **H1b at 100 and 250 m (key test):** ratio of geometric means, shortest vs longest third of 72 h transport distance (terciles within season and height), per season.

**Decoupling criterion (fixed in advance).** At 500 m the winter H1b ratio was 0.86 (0.68 to 1.03). The decoupling explanation predicts that slow near-surface air *is* more polluted. Judged on the **100 m winter H1b ratio**:
- **supported** if it is above 1 with a 95% interval that excludes 1;
- **partly supported** if it is above 1 with an interval that includes 1;
- **not supported** if it is 1 or below.

The same rule is reported for 250 m and for the post-monsoon season, descriptively.

## 3. Fire exposure at each height (H3, October–November)

Trajectory-weighted fire exposure is recomputed from the 100 m and 250 m trajectories with exactly the Stage 7 definition:
- 50 km buffer, endpoints at or below 1,500 m;
- detections on the endpoint's PKT day or the day before;
- unique detections;
- the same missing-satellite days.

Reported: the coefficient c on log(1 + exposure) in the Stage 7 model, with its bootstrap interval and the share of year-shifted null coefficients at or above c, for each height.

## 4. Forecasting sensitivity (Section 5.11: trajectory arrival height)

- **Model:** the full model (L5) and L1 + trajectories, rerun with trajectory features from 100 m and from 250 m in place of 500 m. The Stage 8 engine is used with zero embargo; everything else, including in-fold k-means (k = 6), is unchanged.
- **Reported**, on each run's common weeks (all weeks and Oct–Jan):
  - MAE of each model;
  - the L5 − L4 difference;
  - the L1 + trajectories − L1 difference.
- The difference uses 4-week moving-block bootstrap intervals, as in Stages 4 and 8.
- **Conclusion check:** "the trajectory layer gives no reliable gain" holds at a height if the L5 − L4 interval includes zero.

## 5. Outputs

- **Code:** `src/stage9b_multiheight.py`, with synthetic-data tests (nearest-centre assignment, input checks).
- **Outputs:** `results/tables/stage9b/`. **Report:** `results/tables/stage9b_multiheight_report.md`.
- **Paper:**
  - Section 6.3 / 6.4 (one paragraph and a small table), Section 6.8 (forecast sensitivity), Section 7.2 (decoupling) and the limitations;
  - the "trajectories arriving at 100 and 250 m are planned" sentences are replaced with the results.
- **Not done:** other arrival times, other meteorology (GDAS or ERA5) and CWT maps at the new heights.
