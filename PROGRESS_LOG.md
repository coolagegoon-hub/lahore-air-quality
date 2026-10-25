# Progress Log

## 2026-10-18 — Workspace setup

### Completed
- Workspace setup only: folder structure (with `.gitkeep` placeholders), `CLAUDE.md`, `README.md`, `PROGRESS_LOG.md`, `requirements.txt`, and `.gitignore` created.

### Not completed
- Data acquisition
- Feature engineering
- Modeling
- Evaluation
- SHAP analysis

### Next milestone
- Obtain and quality-control historical Lahore PM2.5 data.

## 2026-10-18 — Stage 1A: PM2.5 source audit

### Completed
- Audited AirNow/State Dept., OpenAQ, Punjab EPD and IQAir. See `results/tables/source_audit.md`.
- Selected OpenAQ location 8664 (US Diplomatic Post: Lahore) as the primary candidate. A one-day cross-check against the original AirNow data found hourly discrepancies.

## 2026-10-18 — Stage 1B: OpenAQ 8664 download and coverage QC

### Completed
- Created project `.venv` and installed `requirements.txt`. Added `certifi` (needed for HTTPS certificate verification with python.org macOS Python).
- Downloaded all 1,909 daily files (2019-05-23 → 2025-03-04) to `data/raw/openaq/location_8664/`. Each file verified by size and MD5 against the S3 listing; manifest with SHA-256 saved.
- Added `src/download_openaq.py`, `src/pm25_qc.py`, `src/run_openaq_coverage.py`, `tests/test_pm25_qc.py` (9 unit tests on synthetic data, all passing).
- Coverage: 1,464 of 2,113 days meet the ≥18/24 valid-hour rule. 2022 is poorly covered (99 complete days). Smog seasons 2021–22 and 2022–23 are largely missing.
- Repeated-value diagnostics: OpenAQ repeat rate is 22.4% vs 4.4% in the original AirNow data for the one comparable window (Sept 2021). There is a 120-hour stuck value (67.0 µg/m³) from 2024-05-31 to 2024-06-05.
- Report: `results/tables/openaq_8664_coverage_report.md`.

### Not completed
- Stuck-value rule, weekly-target validity rule and hour-labelling convention (awaiting decisions).
- OpenAQ licence/terms check.
- Feature engineering, modeling, evaluation, SHAP analysis.

### Next milestone
- Decide the QC rules listed in §6 of the coverage report, then build the weekly PM2.5 target series.

## 2026-10-18 — Stage 1C: data-quality decisions (no model)

### Completed
- Verified the timestamp conventions from documentation:
  - OpenAQ: time-ending, daily 01:00–00:00 local;
  - AirNow: GMT begin-hour; daily midnight-to-midnight, begin-hour, local standard time.
- The existing QC day assignment (00:00 → previous day) matches both conventions.
- Added `src/airnow_archive.py`: extracts the Lahore lines (AQS 586PK3010003) from the public AirNow archive, cached in `data/raw/airnow_files/`.
  - Daily: `daily_data_v2.dat` for 2019-05-22 → 2025-03-06 (2,116 files; 1,778 Lahore daily values).
  - Hourly: 18 eight-day windows (3,456 hours).
- Added `src/stage1c_analysis.py`:
  - repeat-run inventory (3,203 runs ≥ 2 h);
  - S0/S6/S7 exclusion sensitivity;
  - OpenAQ-vs-AirNow hourly and daily comparison;
  - weekly 7/7, ≥6/7, ≥5/7 counts by year and smog season;
  - exhaustive missing-day error for weekly means.
- `src/pm25_qc.py` unchanged; raw OpenAQ files unchanged.
- Key findings (original-source comparison):
  - The 2024-05-31 → 06-05 run of 67.0 is absent from AirNow, so it is not a measurement.
  - OpenAQ hour labels are aligned in some periods, one hour early in 2023-07 → 2024-01, and mixed in 2019-11 → 2021-07. The mixed periods explain the high 2020–2021 repeat rates (only 22 of 191 checked runs exist in AirNow).
  - Daily means still agree with AirNow (r ≥ 0.997).
- Last valid observation: 2025-02-18 18:00 PKT (OpenAQ) and 2025-02-17 (AirNow daily). No Lahore records were found in monthly samples through 2026-10, so the record supports retrospective evaluation only.
- Terms reviewed: OpenAQ platform terms and AirNow Data Exchange Guidelines. Open concerns: whether anonymous S3 download counts as authorized use, and the AirNow preliminary-data and attribution requirements.
- OpenAQ location 6506 could not be resolved (no Explorer page, no archive files, no API key).
- Tests: `pytest -q tests` → 16 passed (9 existing + 7 new, synthetic data only).
- Report: `results/tables/stage1c_data_quality_decisions.md`; tables in `results/tables/stage1c/`.

### Not completed
- Choice of primary hourly source (OpenAQ vs full AirNow archive rebuild), run-exclusion rule and weekly threshold (awaiting decisions).
- AirNow daily completeness criterion not documented.
- Exact dates of the OpenAQ alignment changes not determined.
- Feature engineering, modeling, evaluation, SHAP analysis.

### Next milestone
- Decide the items in §7 of the Stage 1C report, then build the final weekly PM2.5 target series (Stage 2 not started).

## 2026-10-18 — AirNow hourly archive download (option b)

### Completed
- Added `src/airnow_bulk.py`: size-verified bulk extraction of AQS 586PK3010003 lines from AirNow `HourlyData_*.dat` files. Downloads are checked against the S3-listed size and Content-Length; cache files are written atomically; there is one manifest per year in `data/raw/airnow_files/manifests/`. Tests: 2 added (`pytest -q tests` → 18 passed at that time).
- Downloaded all 50,424 hourly files, GMT 2019-05-21 00:00 → 2025-02-18 23:00 (~51 GB transferred; only Lahore lines kept, 182 MB on disk including filesystem overhead).
  - The first pass had 120 network failures in 2023 (Apr 22–23, Oct 12–14, Nov 28–30). A rerun fetched all 120 (0 failures).
  - Manifest statuses: 46,872 verified (size matched); 3,552 cached before the verification step existed (Stage 1C sample weeks); 0 failed.
- Lahore present in 43,231 of 50,424 hourly files. By GMT year: 2019 98.5%, 2020 98.8%, 2021 77.1%, 2022 68.1%, 2023 91.2%, 2024 84.0%, 2025 97.5%. No file had more than one Lahore line.
- The plan to download 2024–2025 on a second computer was abandoned; everything was downloaded on this Mac. The kit `airnow_2024_2025_bundle.zip` (project root) is no longer needed.

### Not completed
- The hourly AirNow series has not been built or QC'd yet: values, time conversion to PKT hour-ending, 18/24 daily rule, comparison with OpenAQ.
- Weekly threshold and run-exclusion rule still undecided; Stage 2 not started.

## 2026-10-18 — AirNow hourly series rebuilt (no Stage 2)

### Completed
- Added `src/airnow_hourly_series.py` and `tests/test_airnow_hourly_series.py` (9 tests). `src/pm25_qc.py` and `src/stage1c_analysis.py` were reused unchanged.
- Built the hourly series in PKT hour-ending time for local days 2019-05-22 → 2025-02-18 (50,400 hours). It has 43,151 valid hours and 1,777 complete days (≥ 18/24). The 61 negative values are invalid under the project rule; keeping them would give 1,780 complete days.
- Time convention verified: rebuilt daily means match AirNow's own published daily values within 0.5 µg/m³ on 99.5% of 1,778 days (MAE 0.083), against 22.6% for the alternative grouping.
- Compared with OpenAQ 8664 on the same days:
  - complete days: 1,777 vs 1,464 (318 AirNow-only; the 5 OpenAQ-only days are the 2024 stuck 67.0 values);
  - common days: r = 0.9987, MAE 2.58 µg/m³;
  - OpenAQ hour labels by month: 28 aligned, 32 mixed, 4 shifted.
- Weekly full weeks with 7/7, ≥ 6/7, ≥ 5/7 complete days: AirNow 220/236/246 of 299 (smog seasons 84/88/92 of 105), OpenAQ 145/178/200 (66/75/79).
- Tests: `pytest -q tests` → 84 passed.
- Report: `results/tables/airnow_rebuild_report.md`.

### Not completed / decisions pending
- Adopt the AirNow rebuild as the primary input; negative-value rule; S6/S7 rule (now 2 AirNow runs); weekly threshold. Stage 2 not started.

## 2026-10-18 — Decision: primary PM2.5 series

- **Adopted:** the AirNow rebuild (AQS 586PK3010003) is the primary PM2.5 series, with negative values invalid (1,777 complete days, 2019-05-22 → 2025-02-18).
  - Files: `data/processed/airnow_586PK3010003_hourly.csv`, `…_daily_18of24.csv`.
  - OpenAQ 8664 is retained for comparison only.
  - Recorded in CLAUDE.md (data rules), README and `results/tables/airnow_rebuild_report.md` §6.
- **Still pending (user to decide separately):** weekly completeness threshold (7/7, ≥ 6/7, ≥ 5/7); run-exclusion rule (S6/S7; affects AirNow runs on 2020-05-03 and 2024-05-25); possible plausibility rule for the 2024-01-26 → 28 near-zero cluster.
- Stage 2 not started.

## 2026-10-20 — Decisions and Stage 2 (weekly target + baselines; no ML model)

### Decisions (user)
- Weekly threshold: ≥ 6 of 7 valid days.
- Repeated-value rule: runs of ≥ 7 h invalid.
- Both recorded in CLAUDE.md (data rules) and `results/tables/forecasting_design.md` §6.

### Completed
- Added `src/stage2_weekly.py` and `tests/test_stage2_weekly.py` (5 tests).
- Run rule: removed 9 hours (the 2020-05-03 run at 24.0), giving 1,776 complete days.
- Weekly target: 235 of 299 full weeks eligible (220 with 7/7, 15 with 6/7; 88 in smog seasons), written to `data/processed/pm25_weekly_target.csv`.
- Baselines scored walk-forward on eligible weeks. On the common set of 138 weeks: persistence MAE 37.8 / RMSE 59.9; climatology MAE 34.0 / RMSE 50.8 (µg/m³). Smog season MAE: persistence 67.0, climatology 55.5. Climatology parameters are provisional (±2 weeks, ≥ 2 years, ≥ 4 weeks).
- Tests: `pytest -q tests` → 89 passed.
- Report: `results/tables/stage2_weekly_target_report.md`.

### Not completed
- PM2.5-history-only baseline model; climatology parameters and persistence max-age not finalised.
- ERA5, FIRMS, HYSPLIT inputs (accounts needed), features, ML model, SHAP.

## 2026-10-20 — PM2.5-history baseline model; input sources chosen

### Decisions (user)
- Historical PM2.5 is the reference baseline; ERA5 is the weather input; NASA FIRMS is the fire-detection input. Prefer locally measured or validated PM2.5 whenever available. Recorded in CLAUDE.md.

### Completed
- Added `src/history_model.py` and `tests/test_history_model.py` (5 tests): a walk-forward Ridge model on past weekly PM2.5 plus calendar harmonics, refitted per target week, with design fixed in advance.
- On 133 common eligible weeks (MAE, µg/m³): history model 30.5, climatology 33.7, persistence 36.4. Smog season: 56.1 / 55.8 / 64.9.
- Validated-data check: no validated Lahore record found; AirNow says embassy data are preliminary.
- Verified access requirements for ERA5 (CDS account, token, dataset licence acceptance, `cdsapi`) and FIRMS (free MAP_KEY by email; area API 1–5 days per request; 5,000 transactions per 10 min).
- Tests: `pytest -q tests` → 94 passed.

### Not completed
- ERA5 and FIRMS downloads (waiting for the user's account and key), features, ML model, SHAP.
- Whether HYSPLIT and the one-box mass-balance features (listed in CLAUDE.md's objective) remain in scope: not yet confirmed by the user.

## 2026-10-20 — ERA5 weather downloaded

### Completed
- Added `src/download_era5.py`, which uses `cdsapi` (added to requirements.txt; credentials are in the git-ignored `.env`, never printed).
- Dataset: `reanalysis-era5-single-levels-timeseries` (ERA5 hourly time series, single levels). Point requested 31.56 N 74.34 E; ERA5 returned its nearest grid point, 31.50 N 74.25 E.
- 19 variables: u100, v100, u10, v10, fg10, d2m, t2m, blh, cbh, msl, skt, slhf, sp, sshf, ssrd, strd, tcc, tp, fdir. The user's 4 ocean-only variables were dropped.
- One request per year: the full-period request was refused ("cost limits exceeded").
- Result: 7 zip files in `data/raw/era5/` (4.23 MB), each with a provenance JSON (request, times, size, SHA-256; all checksums verified).
  - 51,864 hourly rows, 2019-04-01 00:00 → 2025-02-28 23:00 UTC; no missing hours, no duplicates.
  - Only cbh (cloud base height) has blanks (41.7%), meaning no cloud.
- Units are ERA5 native: K, Pa, m, J m⁻² accumulations, m of precipitation. Conversion and the UTC→PKT shift are not done yet.

### Not completed
- ERA5 processing into weekly features; FIRMS (key needed); features, ML model, SHAP.
- The CDS key was pasted into chat; the user was advised to regenerate it.

## 2026-10-21 — ERA5 previous-week weather features

### Completed
- Added `src/era5_features.py` and `tests/test_era5_features.py` (5 tests).
- Processing: UTC → PKT; instantaneous variables assigned to the PKT date of their valid time; hourly accumulations (tp, ssrd, sshf) assigned to the PKT date of valid_time − 1 h. Units converted (°C, hPa, mm, W m⁻²); derived wind speed (10 m, 100 m), relative humidity (Magnus) and calm hours (10 m wind < 1 m/s).
- Daily file `data/processed/era5_daily_pkt.csv`: 2,160 complete PKT days; only the two partial edge days are incomplete.
- Weekly file `data/processed/era5_prev_week_features.csv`: 21 features per target week, taken only from week T−1 (Mon–Sun PKT before the cutoff). All 301 target weeks have features. No imputation.
- Plausibility (monthly means): January 11.3 °C, June max 39.7 °C, July rain 166 mm per 30 days, boundary layer ~200 m in Dec–Jan and ~860 m in May.
- Documented assumption: ERA5 is published days after real time, so it stands in for operational analyses available at the cutoff.
- Tests: `pytest -q tests` → 99 passed.

### Not completed
- FIRMS features (download finishing), HYSPLIT (other laptop), mass-balance features, ML model, SHAP, paper.

## 2026-10-21 — NASA FIRMS fire detections downloaded

### Completed
- Added `src/download_firms.py`. It uses the FIRMS area API with a key in the git-ignored `.env` (never printed or logged).
- Sources: the standard-processing (science-quality) archives VIIRS_SNPP_SP, VIIRS_NOAA20_SP and MODIS_SP.
- Box: 69–78 E, 27–35 N. Dates: 2019-04-01 → 2025-02-28 (UTC acquisition dates). 433 five-day chunks per source.
- Saved to `data/raw/firms/<SOURCE>/`, with a manifest per source (rows, bytes, SHA-256).
- Verification: all 3 × 433 chunks present; 0 checksum mismatches; all dates inside the requested range.
  - Detections: VIIRS SNPP 878,455 (68.0 MB); VIIRS NOAA-20 902,661 (71.7 MB); MODIS 170,868 (13.2 MB).
  - Seasonal pattern as expected for crop-residue burning: peaks in November and October (rice) and May (wheat), low in July–September.

### Not completed
- Fire features: the source-region definition needs user review. HYSPLIT (other laptop), mass-balance features, ML model, SHAP, paper.

## 2026-10-21 — FIRMS previous-week fire features

### Completed
- Added `src/firms_features.py` and `tests/test_firms_features.py` (4 tests). Design approved by the user (2026-10-21).
- Detections used: VIIRS_SNPP_SP; vegetation fires only (type 0); nominal/high confidence. Kept 740,436 of 878,455 (dropped 120,835 low-confidence, 17,327 non-vegetation).
- Times: UTC → PKT date.
- Regions (distance and bearing from the monitor): rings 0–100, 100–300, 300–500 km; sectors east_se (45–180°) and west_s (180–315°) within 500 km. The 300–500 km ring is truncated to the east and north by the download box.
- Outputs: daily file `data/processed/firms_viirs_snpp_daily_pkt.csv`; weekly file `data/processed/firms_prev_week_features.csv` (10 features: count and FRP per ring/sector, from week T−1 only). All 301 target weeks covered.
- Cross-check against VIIRS NOAA-20 (same rules): weekly counts r = 0.97–0.99, NOAA-20 about 3% higher.
- Seasonal pattern: east/southeast detections peak in November (197,554 over all years) and October/May, consistent with crop-residue burning in Indian Punjab and Haryana.
- Limitation: FIRMS does not flag missed passes (cloud, outages), so zero means "none detected".
- Tests: `pytest -q tests` → 103 passed.

### Not completed
- HYSPLIT (user, other laptop), mass-balance features, combined feature table, main ML model, SHAP, paper.

## 2026-10-21 — One-box mass-balance features

### Completed
- Added `src/mass_balance_features.py` and `tests/test_mass_balance_features.py` (4 tests).
- One-box model: C_ss = q·L/(u·H). The features describe dispersion only; emissions are not modelled.
- Inputs: hourly ERA5 boundary-layer height (H) and 10 m wind (u).
- Features from week T−1 only (`data/processed/mass_balance_prev_week_features.csv`; all 301 target weeks covered):
  - ventilation coefficient (all hours and night PKT 18–06);
  - box concentration index 1000/max(VC, 10);
  - median flushing time with L = 30 km;
  - hours with VC < 1000 m²/s.
- Assumptions (project-defined, fixed in advance): L = 30 km, VC floor 10 m²/s, u floor 0.1 m/s, low-ventilation threshold 1000 m²/s.
- Plausibility: median hourly VC ~98–120 m²/s in Dec–Jan vs ~780 in July. The low-ventilation threshold flags 57–89% of hours across months, so it is only moderately discriminating.
- Descriptive association (not a model result, not causal): Spearman ρ with the following week's PM2.5 is 0.715 (low-vent hours), 0.686 (box index) and −0.672 (night VC). Seasonality is a confounder.
- Tests: `pytest -q tests` → 107 passed.

### Not completed
- HYSPLIT (user, other laptop), combined feature table, main ML model, SHAP, paper.

## 2026-10-21 — Stage 3: main model (Random Forest), layered inputs

### Completed
- Added `src/main_model.py` and `tests/test_main_model.py` (4 tests).
- Walk-forward Random Forest (300 trees, leaf 5, max_features 0.33, fixed seed), refitted per target week. Layers: L1 history → L2 + ERA5 → L3 + FIRMS → L4 + mass balance.
- Common set: 133 eligible weeks (52 smog), MAE in µg/m³:
  - persistence 36.4, climatology 33.7, Ridge history 30.5;
  - RF L1 30.2, L2 29.8, L3 29.4, L4 29.3.
  - Smog season: RF L4 51.1 vs Ridge 56.1, climatology 55.8, persistence 64.9.
- Block bootstrap (95% CI):
  - RF L4 beats persistence (all: −7.1 [−12.9, −2.3]; smog: −13.8 [−25.7, −2.5]) and climatology (all: −4.4 [−8.3, −1.8]).
  - vs Ridge history: inconclusive (−1.2 [−6.4, +2.4]). Each input layer's gain is inconclusive.
- RF under-predicts smog-season peaks (bias about −27).
- Report: `results/tables/stage3_model_report.md`.
- Tests: `pytest -q tests` → 111 passed.

### Not completed
- HYSPLIT layer (user, other laptop); pre-declared follow-up model variants; SHAP; figures; paper.

## 2026-10-21 — Stage 3b: pre-declared follow-up models

### Completed
- Wrote the pre-declaration (`results/tables/stage3b_predeclaration.md`) before fitting.
- Added `src/followup_models.py` and `tests/test_followup_models.py` (5 tests). Outputs in `results/tables/stage3b/`; results appended to `stage3_model_report.md` §6.
- rflog (RF on log PM2.5, OOB smearing) L4: MAE 29.6, smog bias −25.8. It did not fix the peak under-prediction; vs RF L4: +0.3 (−0.5, +1.5).
- ridgeall (Ridge, all features) L1→L4: MAE 30.5 → 34.3, RMSE 47.1 → 56.2 (worse as inputs are added; likely overfitting).
- No model reliably beats the Ridge PM2.5-history model; no added input shows a reliable gain.
- Tests: `pytest -q tests` → 116 passed.

### Not completed
- HYSPLIT layer (user, other laptop); SHAP; figures; paper.

## 2026-10-21 — Data figures for the paper

### Completed
- Added `src/figures_data.py`. Outputs are PNG (300 dpi) and PDF in `results/figures/`:
  - fig1_weekly_pm25: weekly PM2.5, 235 eligible of 299 weeks, smog seasons shaded, peak 438 µg/m³ (week of 2024-11-04).
  - fig2_seasonal_cycle: small multiples by month: PM2.5 boxplots, VIIRS fires by sector, median ventilation coefficient, ERA5 rainfall.
  - fig3_fire_map: VIIRS vegetation-fire density with the 100/300/500 km rings and sector lines. No borders (no offline boundary data).
  - fig4_data_availability: valid PM2.5 hours per day by year (1,776 of 2,100 days ≥ 18 h).
- Colours: dataviz reference palette (categorical blue/orange slots 1–2, sequential blue ramp). The palette validator could not be run (Node.js not installed); the palette's documented validation was relied on, and labels/legends are on every figure.
- Each figure was rendered and inspected; the fig3 label placement was fixed after inspection.

### Not completed
- Result figures (Stage 3 errors, predicted vs observed) — planned after HYSPLIT; SHAP; paper text.

## 2026-10-21 — Figures: borders and palette validation

### Completed
- Downloaded Natural Earth 1:10m Admin-0 land boundary lines (public domain; 2.28 MB, SHA-256 in `data/raw/natural_earth/*.provenance.json`). Drew them on fig3: solid = international, dashed = disputed / line of control, with a neutrality note in the caption.
- Relabelled the fire sectors as geometric, not national: east/south-east = "mostly Indian Punjab and Haryana" (it also contains Pakistani districts south-east of Lahore); west/south = "mostly Pakistan". Feature definitions are unchanged.
- Ran the dataviz palette validator in the built-in browser (Node.js not installed; served locally, then stopped):
  - blue+orange categorical: PASS all checks under all-pairs (CVD ΔE 24.7, normal 33.6, contrast ≥ 3:1);
  - fig4 ordinal steps: initially FAILED light-end contrast (#9ec5f4, 1.74:1); changed to ramp steps 250/400/600 → PASS (2.06:1);
  - fig3 hexbin uses the full sequential ramp, where the light end may recede (allowed for continuous magnitude).
- All four figures re-rendered and inspected.

## 2026-10-22 — Full recheck and GitHub

### Completed
- Reran the entire pipeline from raw data (11 steps, all exit 0). 61 of 63 output tables were byte-identical. The two Random Forest prediction files differed by ~1e-13 µg/m³ (parallel float summation); they are now written at 6 decimals, and two consecutive full runs give identical files. All reported score and bootstrap tables are byte-identical to the original run.
- Tests: `pytest -q tests` → 116 passed.
- Secrets scan: neither API key appears in any file outside the git-ignored `.env`.
- Git initialised (branch main); `.gitignore` extended with `.pytest_cache/` and `.claude/settings.local.json`. First commit 76fe9a7 (123 files; no raw data, credentials or virtual environment).
- Published by the user via GitHub Desktop as a private repository: github.com/coolagegoon-hub/lahore-air-quality.

## 2026-10-23 — Stage 4: HYSPLIT trajectory features (model layer 5)

### Completed
- Received `hysplit_results.zip` from the HYSPLIT laptop. Stored in `data/raw/hysplit/` (git-ignored).
  - Validated here: 2,161 daily 72 h back-trajectories (06 UTC, 500 m AGL, 2019-04-01 → 2025-02-28), 73 points each, CSV SHA-256 matches the README.
  - HYSPLIT v5.4.2; NCEP/NCAR Reanalysis 2.5°; no failed days.
- Pre-declared the design before fitting (`results/tables/stage4_predeclaration.md`, commit 2a4b644).
- Added `src/trajectory_features.py`, `src/stage4_trajectory_model.py` and `tests/test_trajectory_features.py` (5 tests).
  - k-means (k = 6) is fitted per fold on trajectories arriving before T − 7 days; week T−1 trajectories are only assigned to the fitted centres.
  - Weekly features: cluster shares, mean 72 h distance, east/south-east sector share, mean height.
- Results (133 common weeks, 52 Oct–Jan), MAE in µg/m³:
  - RF L5 29.07 vs L4 29.27; ΔMAE −0.20, 95% CI (−1.22, +0.98). Oct–Jan: −0.27 (−2.67, +2.55). Same with 2- and 8-week blocks.
  - L1 + trajectories vs L1: −1.30 (−3.28, +0.67).
  - k = 4/8: 29.49 / 28.90.
  - L5 beats persistence and climatology; not the Ridge history model.
- Report: `results/tables/stage4_trajectory_report.md`.
- Tests: `pytest -q tests` → 121 passed.

### Not completed
- Trajectory-weighted fire exposure; H1–H3; four-season scheme; embargo options; descriptive clustering; SHAP; results figures.

## 2026-10-23 — Stage 5: SHAP analysis (layer-5 model)

### Completed
- Installed `shap` 0.54.1 (added to requirements.txt). Pre-declared the SHAP design before computing (commit 5e8ef42).
- Added `src/shap_analysis.py` and `tests/test_shap_analysis.py` (4 tests).
- Fold-by-fold out-of-sample SHAP for 228 forecasts, with checks: reproduction error vs Stage 4 4.9e-7; additivity error 2.6e-13.
- Reliance by group, 133 common weeks (mean |SHAP|, share of total):
  - PM2.5 history 27.9 (37.6%), calendar 19.2 (25.8%), ERA5 11.6 (15.6%), mass balance 7.0 (9.4%), fire 6.0 (8.0%), trajectories 2.7 (3.6%).
  - Oct–Jan: trajectories 4.6 (4.7%).
- Top non-history inputs: low-ventilation hours, boundary-layer height, surface pressure.
- Figure `results/figures/fig5_shap_groups.png|pdf`. Report `results/tables/stage5_shap_report.md`.
- Tests: `pytest -q tests` → 125 passed.

### Not completed
- Trajectory-weighted fire exposure; H1–H3; four-season scheme; embargo options; remaining results figures; paper.

## 2026-10-23 — Step 8: results figures

### Completed
- Added `src/figures_results.py`. It draws only from saved walk-forward outputs; no model is refitted. Outputs are PNG (300 dpi) + PDF in `results/figures/`:
  - fig6_mae_by_method: MAE for persistence, climatology, Ridge history and RF L1–L5; all weeks (133) vs Oct–Jan (52).
  - fig7_layer_increments: ΔMAE for each added layer and L5 vs baselines, with 95% block-bootstrap CIs (4-week blocks).
  - fig8_forecast_timeseries: observed vs RF L5 and Ridge-history forecasts over the common set, Oct–Jan shaded.
  - fig9_forecast_vs_observed: RF L5 scatter with 1:1 line (MAE 29.1, R² 0.75).
- Each figure was rendered and inspected; legend and label overlaps in fig7/fig9 were fixed.
- Software: Matplotlib (figures are code, so they can be regenerated after any analysis change).
- Tests: `pytest -q tests` → 125 passed.

## 2026-10-23 — Documentation brought up to date

### Completed
- README rewritten to the current state: purpose, status table, main results, data sources and credits, how to run (pipeline order), folder structure, limitations, and a licence note (none chosen yet).
- Added dated status notes to the superseded or older reports (source audit, OpenAQ coverage report, Stage 1C decisions, forecasting design, AirNow rebuild, Stage 2, Stage 3). Their original text is kept as the historical record.
- Code comments updated: the Monday–Sunday week and ≥ 6/7 threshold are now marked as decided (2026-10-20), not provisional; `src/main_model.py` points to the L5 trajectory layer. No logic changed.
- CLAUDE.md data sources now name the FIRMS product (VIIRS Suomi NPP only) and the HYSPLIT configuration (v5.4.2, NCEP/NCAR Reanalysis 2.5°, 72 h, 06 UTC, 500 m; in-fold clustering).
- Added `requirements-lock.txt` (exact versions from `pip freeze`).
- Email to AirNow (dmc@airnowtech.org) asking about the causes of the long data outages was sent by the user on 2026-10-23; no reply yet.
- Tests: `pytest -q tests` → 125 passed.

### Open
- Optional analyses: trajectory-weighted fire exposure, H1–H3 association tests, four-season scheme, embargo options.
- Licence choice and whether to make the repository public.
- Paper (step 9, brainstorming).

## 2026-10-23 — Repository made runnable from GitHub alone

### Found (fresh clone from GitHub, new environment)
- Install and tests worked (125 passed), but `pip install -r requirements.txt` picked pandas 3.1.0, which changes a few results in the 14th decimal place and warns about renamed date functions.
- `src.stage2_weekly` rebuilt the hourly series from the AirNow archive, which needs the ~51 GB download, although its input is already committed in `data/processed/`.
- The HYSPLIT trajectories (needed for L5 and SHAP) and the Natural Earth borders (figure 3) existed only on this Mac, and the README pointed to a HYSPLIT README that was not in the repository.

### Changed
- `src.stage2_weekly` now reads the committed hourly file through the new `airnow_hourly_series.load_saved_grid()`. Checked: it is identical (exact comparison) to the archive rebuild.
- Added to the repository: `data/raw/hysplit/` (endpoints CSV, README with settings, met manifest, scripts, feasibility notes; the zip copy is left out) and `data/raw/natural_earth/` (public domain). `.gitignore` has exceptions for these two folders only.
- Renamed `dayofweek` → `day_of_week` and `dayofyear` → `day_of_year` (deprecated in pandas 3.1).
- PDF figures no longer store a creation date, so reruns write byte-identical files. Figure 5's PDF was redrawn from the saved SHAP values: the summary matches `shap_group_summary.csv` and the PNG is byte-identical to the previous one.
- README: install from `requirements-lock.txt`; a table of which steps need a raw download (their outputs are committed); what is included in `data/raw/`.

### Checked
- Full local rerun of all 12 pipeline steps with the locked versions: every table, processed data file and PNG identical to the committed ones; the PDFs differed only in the creation date. Wall-clock times (the Mac may have slept during some): main model ~19 min, follow-up models ~22 min, Stage 4 ~4.3 h, SHAP ~1.2 h, data figures ~11 min.
- Fresh clone of this commit in a new environment: `pip install -r requirements-lock.txt` gave the locked versions; 125 tests passed; `stage2_weekly`, `history_model` and `main_model` ran with no download (main model 161 s) and reproduced the committed files exactly; the HYSPLIT endpoints (2,161 trajectories) and borders load. The clone's rerun of the follow-up models, Stage 4 and SHAP was stopped at the user's request; those steps were checked by the full local rerun above.
- Tests: `pytest -q tests` → 125 passed.

## 2026-10-23 — Licences and data terms

### Completed
- Licences chosen by the user: **MIT** for code (`LICENSE`) and **CC BY 4.0** for everything else made for the project (`LICENSE-CC-BY-4.0.txt`, official text from creativecommons.org). Copyright © 2026 Sardar Zayaan Akhtar Nakai. Third-party data are excluded.
- README "Data sources and credits" now gives each provider's terms and required credit, checked against the providers' own pages on 2026-10-23:
  - AirNow Data Exchange Guidelines (PDF, last updated August 2025);
  - OpenAQ terms of use;
  - the ERA5 time-series catalogue entry (DOI 10.24381/1cf1ad76, licence CC-BY-4.0);
  - the NASA Earthdata FIRMS page (acknowledgment sentence);
  - the NOAA HYSPLIT page (Stein et al. 2015);
  - Natural Earth terms of use (public domain).
- Finding: the AirNow guidelines say publications that rely on AirNow data "must be made known" to the data owner and the AirNow program, and they include a form to sign and email to dmc@airnowtech.org agreeing to the guidelines. This is a notification, not a permission request. They also ask that validated data be used whenever possible (none exists for this monitor; see CLAUDE.md).

### Open
- Notify AirNow (and the U.S. Department of State as data owner) about the project before publishing; the user decides whether to also return the guidelines form.
- Whether to make the repository public.

## 2026-10-25 — Stage 6: AirNow backfill for September 2022, full rerun

### Completed
- AirNow's Data Management Center (Marcus Hylton, email of 2026-10-23) explained the three long gaps: 21 Oct – 7 Dec 2021 not received (cause unknown); 6 Sep – 1 Oct 2022 backfilled after the archive was written; 26 May – 29 Jun 2024 partly unreceived and partly withheld after QA (unchanging values).
- Downloaded AirNow's regenerated file `Lahore_PM2.5_2022_09_MTD.csv` to `data/raw/airnow_embassy_historical/` (with provenance and SHA-256). Timing check before any rerun: all 81 overlapping hours identical with labels read as hour-ending PKT.
- Pre-declared the change (`results/tables/stage6_backfill_predeclaration.md`, commit c081b10) before rebuilding: archive rows stay primary; backfill fills only absent hours; disagreement stops the build.
- `src/airnow_hourly_series.py`: `load_backfill()` and `merge_backfill()`; 3 new synthetic tests.
- Reran all 12 pipeline steps (about 7 minutes; the Mac was kept awake). Tests: `pytest -q tests` → 128 passed.
- Results (`results/tables/stage6_backfill_report.md`): +599 valid hours; 1,801 complete days; 239 eligible weeks; common set 138 weeks (53 Oct–Jan). MAE: persistence 35.5, climatology 32.6, Ridge 29.7, RF L1–L5 29.2 / 28.9 / 28.1 / 28.7 / 28.4. L5 vs L4 −0.37 (−1.30, +0.77). Fire layer (L3 vs L2) −0.74 (−1.90, −0.01), narrowly excluding zero over all weeks only. SHAP shares essentially unchanged.
- Added dated notes to the earlier reports; README updated.
