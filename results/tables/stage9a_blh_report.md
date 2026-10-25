# Stage 9a — Boundary-Layer Height vs Trajectory Arrival Height: Results

- **Date:** 2026-10-25
- **Design:** pre-declared in `stage9a_blh_predeclaration.md`, approved by the user and committed (`69de915`) before any Stage 9a code was run. Every pre-declared quantity is reported.
- **Code:** `src/stage9a_blh_check.py` (test: `tests/test_stage9a_blh_check.py`). **Output:** `results/tables/stage9a/blh_below_arrival_height.csv`.
- **Data:** ERA5 hourly BLH at 31.50° N, 74.25° E, PKT days 1 April 2019 to 28 February 2025, no missing hours. Daily PM2.5 for item 3: Stage 7 analysis days (AirNow, **preliminary**; U.S. Department of State / EPA AirNow).
- **Interpretation:** descriptive frequencies of a model field. ERA5 BLH has not been checked against observations over Lahore.

## Results

| | Winter | Pre-monsoon | Monsoon | Post-monsoon | Oct–Jan |
|---|---|---|---|---|---|
| Hours | 13,008 | 12,499 | 17,568 | 8,784 | 17,712 |
| % of all hours with BLH < 500 m | 81.8 | 66.6 | 63.3 | 76.1 | 80.0 |
| % of all hours with BLH < 250 m | 72.9 | 57.1 | 48.0 | 69.3 | 72.0 |
| % of all hours with BLH < 100 m | 61.2 | 39.9 | 26.6 | 57.5 | 60.6 |
| Days | 542 | 521 | 732 | 366 | 738 |
| **% of days with BLH < 500 m at 06 UTC (11:00 PKT)** | **78.0** | 3.8 | 3.3 | 21.3 | 53.5 |
| % of days with BLH < 250 m at 06 UTC | 21.6 | 0.2 | 0.0 | 0.3 | 14.4 |
| % of days with BLH < 100 m at 06 UTC | 2.8 | 0.0 | 0.0 | 0.0 | 2.0 |
| Median BLH at 06 UTC, m (IQR) | 368 (270–472) | 1,201 (830–1,758) | 1,094 (873–1,388) | 712 (520–952) | 473 (321–737) |
| Lowest third of daily PM2.5: % of days with BLH < 500 m at 06 UTC | 62.3 (159 days) | 3.9 (129) | 6.6 (211) | 12.6 (103) | — |
| Highest third of daily PM2.5: % of days with BLH < 500 m at 06 UTC | **92.4** (158 days) | 3.1 (128) | 0.9 (211) | 23.3 (103) | — |

## Reading

- **Winter:** at the trajectories' arrival time, the 500 m arrival point lay above ERA5's boundary layer on 78% of days. On the most polluted third of winter days it did so on 92% of days, against 62% on the cleanest third. On most winter days, and especially on polluted ones, the 500 m trajectories therefore describe air above the layer the surface monitor samples. This supports the decoupling explanation offered in the paper for why slow trajectories were not more polluted.
- **Post-monsoon (October–November):** the 500 m arrival point was above the boundary layer on about a fifth of days (21%; 23% on the most polluted third). On most days it lay within the mixed layer.
- **Pre-monsoon and monsoon:** almost never (under 4%).
- **Lower heights:** at 06 UTC, a 250 m arrival point would be above the boundary layer on 22% of winter days, and a 100 m point on 3%. The planned 100 m and 250 m trajectories (Stage 9b) would therefore sit inside ERA5's mixed layer on most winter days.
- **All hours:** over all hours (including nights), BLH is below 500 m most of the time in every season (63–82%). A trajectory arriving at night would almost always be above the mixed layer at 500 m. This is a reason to compare heights at the 06 UTC arrival time rather than at night.
