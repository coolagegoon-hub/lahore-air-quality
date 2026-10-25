# Stage 9a — Pre-declared Design: How Often Is the Trajectory Arrival Height Above the Boundary Layer?

- **Declared:** 2026-10-25, before any of these shares was computed.
- **Status:** approved by the user on 2026-10-25 ("I approve the Stage 9a plan and the laptop files. Commit them, push so the laptop can pull them, and run the boundary-layer check."). Committed before any Stage 9a code was run.
- **Why:** a review argued that the 500 m arrival height may lie above the shallow surface layer where Lahore's smog builds up. If so, the trajectories would describe air that the monitor does not breathe. The paper already offers this as a possible reason why slow (short-distance) trajectories were not more polluted (Section 7.2). This check measures how often it can happen, using ERA5 data already downloaded. No new data, models or trajectories are needed.
- **Scope:** descriptive only. Nothing in Stages 1–8 changes. This is not a forecast, and it does not attribute sources.

## 1. Data

- **ERA5 hourly boundary-layer height** (BLH, m above ground) at the grid point nearest the monitor (31.50° N, 74.25° E). Same file and conversion as `src.era5_features.to_hourly_pkt`, with hours assigned to PKT days.
- **Period:** 1 April 2019 to 28 February 2025, the same days as the trajectories.
- **Seasons (by PKT date, as in Stage 7):**
  - winter: December–February;
  - pre-monsoon: March–May;
  - monsoon: June–September;
  - post-monsoon: October–November.
- Daily PM2.5 for item 3: the Stage 6 daily means (AirNow, **preliminary**; credit the U.S. Department of State and the EPA AirNow program).

## 2. Quantities (all per season, and for October–January as a secondary split)

1. **Share of all hours** with BLH below 500 m. The same share is also reported for 250 m and 100 m, the heights of the planned extra trajectories.
2. **Share of days with BLH below 500 m at the trajectory arrival time**, 06 UTC (11:00 PKT), the arrival time of all trajectories. The same shares are reported for 250 m and 100 m.
3. **By pollution level:** among the Stage 7 analysis days (a complete daily mean and a trajectory), the share of days with BLH below 500 m at 06 UTC, separately for the lowest and highest third of daily PM2.5 within each season.
4. **Median BLH** at 06 UTC, and its interquartile range.

## 3. Reporting and interpretation

- **Reported:** all shares as percentages, with the number of hours or days behind each.
- No confidence intervals are given, because these are descriptive frequencies of a model field, not estimates of an effect.
- **Interpretation:** when BLH at the arrival time is below the arrival height, the trajectory's end point lies above ERA5's mixed layer. Its path then describes air above the layer the surface monitor samples.
  - High shares in the polluted seasons would support the decoupling explanation and limit what the 500 m trajectories can say about surface air.
  - Low shares would argue against it.
- **No threshold** (such as the review's suggested 40 to 50%) is used to decide anything. The shares are reported and discussed as they are.
- **Caveats (stated in the paper):**
  - ERA5 BLH is a model estimate on a grid of about 31 km and has not been checked against observations over Lahore.
  - Heavy aerosol can itself lower the boundary layer.
  - Item 3 is an association within seasons, not a cause.

## 4. Outputs

- **Code:** `src/stage9a_blh_check.py`, with a synthetic-data test.
- **Outputs:** `results/tables/stage9a/`. **Report:** `results/tables/stage9a_blh_report.md`.
- **Paper:** the result goes into Section 7.2 (transport versus local accumulation) and the limitations.

## 5. Not part of Stage 9a

The extra trajectories at 100 m and 250 m (arriving at 06 UTC, as before) are produced on the processing laptop (`data/raw/hysplit/LAPTOP_RUN_multiheight.md`). Any analysis of them will be pre-declared separately, as Stage 9b, before it is run.
