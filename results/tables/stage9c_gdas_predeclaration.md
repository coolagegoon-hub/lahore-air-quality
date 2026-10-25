# Stage 9c — Pre-declared Design: Does Sharper Weather Data (GDAS 1°) Change the Trajectories or the Results?

- **Declared:** 2026-10-25, before any GDAS 1° file was downloaded or any GDAS trajectory computed.
- **Status:** approved by the user on 2026-10-25 ("I approve the Stage 9c plan and laptop files. Commit and push them (with the Stage 9b commit, not the paper) so the laptop can pull them."). Committed before any GDAS file was downloaded.
- **Why:** a review pointed out that the trajectories use NCEP/NCAR Reanalysis at 2.5° (about 250 km), while the weather features use ERA5 at 0.25°. Coarse meteorology could blur real transport pathways and hide a link with PM2.5.
- **What sharper data is realistic:** checked on NOAA ARL's archive on 2026-10-25.
  - GDAS 0.5° ends in June 2019, so it is unusable.
  - GFS 0.25° is about 2.7 GB per day, so it is impractical.
  - **GDAS 1°** is 571 MB per week, with published MD5 checksums. It is the standard HYSPLIT input in published studies and the setting this paper first proposed.
- **Design:** one year is recomputed with GDAS 1° and compared, day by day, with the existing 2.5° trajectories. The one-year GDAS trajectories are a **comparison only**. They never replace or mix with the 2.5° trajectories in the main analysis, because mixing meteorology between years would make the record inconsistent.

## 1. Trajectories to compute (on the processing laptop)

- **Period:** arrivals on the 365 days from **1 March 2024 to 28 February 2025** (PKT days).
  - This year includes the November 2024 episode, the most polluted week in the record.
  - The monitor's gap of 26 May to 29 June 2024 limits the PM2.5 comparison in that window.
- **Meteorology:** NOAA ARL GDAS 1° weekly files (`gdas1.<mon><yy>.w1` … `w5`), from `gdas1.feb24.w4` to `gdas1.feb25.w4` (about 30 GB). Each file is checked against NOAA's `listing.md5.txt` and recorded in a manifest with its size, MD5 and SHA-256.
- **Settings:** identical to the 2.5° run except the meteorology:
  - HYSPLIT v5.4.2;
  - receptor 31.560078 N, 74.33589 E;
  - arrival at 06 UTC;
  - 72 h backward;
  - vertical motion from the met data;
  - model top 10,000 m;
  - HYSPLIT defaults.
- **Heights:** 500 m (primary for this comparison), plus 100 m and 250 m, which cost no extra download.
- **Output:** a separate folder and file. The 2.5° trajectories and their tdump files are never touched. The GDAS files may be deleted after the run is verified; the manifest lets them be re-downloaded exactly.

## 2. Comparison (on the Mac), same days, same arrival heights

**Trajectory agreement (all 365 days, by season):**
- horizontal separation between the GDAS and NCEP endpoints at 24, 48 and 72 h back (median and interquartile range, km), also as a share of the NCEP transport distance;
- Spearman correlation of the 72 h transport distance;
- the share of days assigned to the same Stage 7 cluster (nearest 500 m cluster centre, as in Stage 9b);
- the mean endpoint height.

**Results agreement.** Each key association is estimated twice on the year's analysis days (complete daily PM2.5 and a trajectory), once with NCEP and once with GDAS trajectories, using the Stage 7 methods (7-day block bootstrap, 2,000 resamples, seed 20261025):
1. H1: C2/C1 ratio of geometric mean PM2.5, raw, in winter (Dec 2024–Feb 2025) and post-monsoon (Oct–Nov 2024);
2. H1b: shortest vs longest transport-distance tercile ratio, in the same two seasons;
3. H3: fire-exposure coefficient c in October–November 2024. The model is log PM2.5 ~ log VC + cluster + day of season + c·log(1 + exposure), with no year terms because there is one season.

With one year, intervals will be wide. The aim is to see whether the sharper data moves the estimates, not to re-test the hypotheses.

## 3. Decision rule (fixed in advance)

The sharper data **changes the results substantially** if any of the following holds (500 m, all 365 days, or the year's analysis days for item c):
- **(a)** fewer than 80% of days are assigned to the same cluster;
- **(b)** the Spearman correlation of 72 h transport distance is below 0.8;
- **(c)** for any of the five estimates in Section 2, either:
  - the GDAS point estimate lies outside the NCEP estimate's 95% interval, or
  - the two point estimates fall on opposite sides of the no-effect value (1 for ratios, 0 for c).

**Then:**
- **If none holds:** the main analysis stays on the 2.5° trajectories, and the paper reports this one-year comparison as evidence that the resolution does not change the conclusions.
- **If any holds:** the paper reports the difference. The user then decides between:
  - recomputing the whole record with GDAS 1° (about 180 GB) and redoing the trajectory analyses with it (a new pre-declared stage);
  - dropping the trajectory-based claims that depend on the resolution.

Separations are reported descriptively. No threshold is set for them, because no agreed acceptable separation exists for this setting.

## 4. Outputs

- **Laptop:**
  - `data/raw/hysplit/LAPTOP_RUN_gdas1.md`;
  - `scripts/download_met.py` gains a `--dataset gdas1` option;
  - `scripts/run_trajectories.py` gains a `--dataset gdas1` option.
  - The default behaviour of both scripts is unchanged.
- **Mac:**
  - code: `src/stage9c_gdas_comparison.py`, with synthetic-data tests;
  - outputs: `results/tables/stage9c/`;
  - report: `results/tables/stage9c_gdas_report.md`.
- **Paper:** methods (Section 4.4), results, limitations and the decision.
