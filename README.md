# Lahore PM2.5 Air-Quality Forecasting

## Purpose

This research project tests whether **HYSPLIT back-trajectory clusters, ERA5 meteorology, NASA FIRMS fire activity, historical PM2.5 and simplified one-box mass-balance features** improve forecasts of **weekly mean PM2.5** in Lahore, Pakistan, compared with simple baselines.

Forecasts are evaluated as a **retrospective study (hindcast)**: every week is forecast with a strict chronological walk-forward design that only uses information available before that week. This is a research pipeline, not a live forecasting service. The Lahore monitor used here stopped reporting to AirNow in February 2025.

See [CLAUDE.md](CLAUDE.md) for the binding scientific, leakage, data and integrity rules, and [PROGRESS_LOG.md](PROGRESS_LOG.md) for the dated record of all work.

## Current status (2026-10-23)

**Analysis pipeline complete; paper in preparation.** Done:

| Step | What | Report |
|---|---|---|
| PM2.5 record | AirNow rebuild of the U.S. Consulate Lahore monitor (AQS 586PK3010003), 22 May 2019 – 18 Feb 2025, hourly, quality-controlled | `results/tables/airnow_rebuild_report.md` |
| Weekly target | Monday–Sunday (PKT) mean, eligible with ≥ 6 of 7 valid days; 239 of 299 full weeks | `results/tables/stage2_weekly_target_report.md` |
| Baselines | Persistence, seasonal climatology, Ridge PM2.5-history model | same, §3 and §6 |
| Inputs | ERA5 weather, FIRMS fires, one-box mass balance, HYSPLIT trajectories (all from the week before the forecast) | `PROGRESS_LOG.md` |
| Main model | Walk-forward Random Forest, built up in 5 input layers | `results/tables/stage3_model_report.md`, `stage4_trajectory_report.md` |
| Explanation | Fold-by-fold out-of-sample SHAP, by input group | `results/tables/stage5_shap_report.md` |
| Pathway associations | Descriptive clustering of all trajectories; PM2.5 by pathway, ventilation and trajectory-weighted fire exposure within seasons (H1–H3) | `results/tables/stage7_association_report.md` |
| Figures | 9 figures (data, SHAP, results) | `results/figures/` |

**Main results** (rerun of 2026-10-25 with AirNow's backfilled September 2022 data, see `results/tables/stage6_backfill_report.md`; 138 eligible forecast weeks, 17 May 2021 – 10 Feb 2025, 53 of them Oct–Jan; mean absolute error in µg/m³):

- Persistence 35.5, seasonal climatology 32.6, Ridge PM2.5-history 29.7.
- Random Forest layers:
  - L1 (PM2.5 history) 29.2;
  - L2 (+ ERA5) 28.9;
  - L3 (+ fire) 28.1;
  - L4 (+ mass balance) 28.7;
  - L5 (+ HYSPLIT trajectories) 28.3.
- The full model beats persistence and climatology; 95% block-bootstrap intervals exclude zero.
- It does **not** reliably beat the Ridge PM2.5-history model.
- Only one added layer has an interval that excludes zero, narrowly: fire (L3 vs L2), −0.7 µg/m³, 95% CI −1.9 to −0.01, not in Oct–Jan. Trajectories (L5 vs L4): −0.4 µg/m³, 95% CI −1.3 to +0.8.
- All models under-predict the highest smog-season weeks.
- SHAP: the model relies mostly on recent PM2.5 (38%) and season (26%), then ERA5 weather (16%), mass balance (9%), fire (8%) and trajectories (4%). This describes model reliance, not causes.

**Pathway associations** (Stage 7; 1,801 days; associations only):
- Three trajectory clusters (Ward, pre-declared 30% rule): slow from SE 60%, fast from NW 37%, fast from W 3%.
- Within seasons, fast north-westerly days had higher PM2.5 than slow south-easterly days (ratio 1.16 winter, 1.30 pre-monsoon, 1.09 monsoon, 1.07 post-monsoon), but these differences largely vanish after weather adjustment.
- Ventilation: slope of log PM2.5 on log ventilation −0.47 in winter and post-monsoon (about 5% higher PM2.5 per 10% lower ventilation), weaker in pre-monsoon, none in the monsoon.
- Trajectory-weighted fire exposure (Oct–Nov): positive, about 6% higher PM2.5 per doubling, above all year-shifted nulls.

Analysis designs for Stages 3b, 4, 5, 6 and 7 were written and committed **before** their results were computed (see the `*_predeclaration.md` files and the Git history).

**Not done / open:**
- a four-season scheme;
- embargo options (one week; per-source latency);
- the paper itself.

## Data sources and credits

Each source keeps its own terms. This project's licences (below) do not cover these data.

| Data | Source | Terms and required credit |
|---|---|---|
| PM2.5 | U.S. Department of State monitor at the U.S. Consulate Lahore (AQS 586PK3010003), via the **EPA AirNow** file archive | [AirNow Data Exchange Guidelines](https://docs.airnowapi.org/docs/DataUseGuidelines.pdf) (August 2025). The data are **preliminary** (not fully verified or validated), and every analysis, display or product must say so. Credit the U.S. Department of State and the EPA AirNow program first. Publications that rely on the data must be made known to the data owner and the AirNow program. |
| PM2.5 (comparison only) | OpenAQ location 8664 (the same monitor, via AirNow) | [OpenAQ terms of use](https://docs.openaq.org/about/terms): credit OpenAQ and the original source. Used only to diagnose data issues, never as model input. |
| Weather | **ERA5** hourly time-series data on single levels, Copernicus Climate Change Service (C3S) Climate Data Store, DOI [10.24381/1cf1ad76](https://doi.org/10.24381/1cf1ad76); grid point 31.50 N, 74.25 E | CC BY 4.0. Contains modified Copernicus Climate Change Service information (2026). Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains. |
| Fires | **NASA FIRMS** VIIRS (Suomi NPP) 375 m standard-processing active fires; NOAA-20 used only as a cross-check | NASA open data. NASA asks for this acknowledgment: "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time Capability for Earth observations (LANCE) and NASA's Earth Science Data and Information System (ESDIS)." VIIRS 375 m algorithm: Schroeder et al. (2014), doi:10.1016/j.rse.2013.12.008. |
| Trajectories | Computed for this project with **NOAA ARL HYSPLIT** v5.4.2 (Stein et al. 2015, doi:10.1175/BAMS-D-14-00110.1), driven by **NCEP/NCAR Reanalysis** 2.5° (Kalnay et al. 1996). 72 h back-trajectories, 06 UTC, 500 m AGL; coarse grid, so synoptic scale | The trajectories are this project's own output (CC BY 4.0, below). Cite HYSPLIT and the reanalysis in publications. |
| Map borders | **Natural Earth** 1:10m, figure 3 only | Public domain; no permission needed. "Made with Natural Earth." |

## How to run

Requires Python 3.12 (used for all results). To reproduce the committed results exactly, install the exact package versions from `requirements-lock.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
```

`requirements.txt` lists the same packages without versions. Newer versions should also run, but they can change results in the last decimal places.

### What needs a download

Most steps run from files already in this repository. Four steps need large raw downloads, but their outputs are committed, so you can skip them:

| Step | Needs | Committed output |
|---|---|---|
| `airnow_hourly_series` | The AirNow hourly archive: about 51 GB transferred, of which only the Lahore lines are kept (`src/airnow_bulk.py`); plus AirNow's regenerated September 2022 file, included in `data/raw/airnow_embassy_historical/` | `data/processed/airnow_586PK3010003_*.csv` |
| `era5_features`, `mass_balance_features` | ERA5 time series (`src/download_era5.py`; needs a free Copernicus CDS key: `CDSAPI_URL` and `CDSAPI_KEY` in a local `.env`) | `data/processed/era5_*.csv`, `mass_balance_*.csv` |
| `firms_features` | FIRMS fire archive, about 150 MB (`src/download_firms.py`; needs a free NASA `FIRMS_MAP_KEY` in `.env`) | `data/processed/firms_*.csv` |
| `figures_data` | The ERA5 and FIRMS raw files above | `results/figures/fig1`–`fig4` |

Two small raw inputs are included in `data/raw/`:
- `hysplit/`: the HYSPLIT trajectory endpoints (2,161 daily trajectories), the scripts that made them on a separate Windows machine, and a README with the exact settings. The 8.7 GB of meteorology files are not included; `manifest.csv` lists each one with its NOAA checksum.
- `natural_earth/`: country borders for figure 3 (public domain).

**Never commit `.env`.**

### Pipeline order

Each step writes to `data/processed/` and `results/`:

```bash
python -m src.airnow_hourly_series      # AirNow hourly series, 18/24 daily rule (needs the AirNow download)
python -m src.stage2_weekly             # run rule, weekly target, persistence/climatology
python -m src.history_model             # Ridge PM2.5-history baseline
python -m src.era5_features             # ERA5 previous-week features (needs ERA5)
python -m src.firms_features            # FIRMS previous-week features (needs FIRMS)
python -m src.mass_balance_features     # one-box mass-balance features (needs ERA5)
python -m src.main_model                # Random Forest layers L1–L4
python -m src.followup_models           # pre-declared follow-up models (Stage 3b)
python -m src.stage4_trajectory_model   # HYSPLIT layer L5 (in-fold clustering)
python -m src.shap_analysis             # SHAP (Stage 5)
python -m src.figures_data              # figures 1–4 (needs ERA5 and FIRMS)
python -m src.figures_results           # figures 6–9
python -m pytest -q tests               # 125 tests, synthetic data only
```

All outputs are deterministic. With the versions in `requirements-lock.txt`, rerunning the steps that need no download reproduces the committed files exactly.

## Folder structure

```
data/
  raw/          Raw inputs, never edited by hand (git-ignored except hysplit/ and natural_earth/)
  processed/    Cleaned data and features produced by code
src/            Pipeline modules (see "How to run")
tests/          pytest tests (synthetic data only)
results/
  figures/      Figures 1–9 (PNG 300 dpi + PDF)
  tables/       Result tables and stage reports (*_report.md, *_predeclaration.md)
models/         Unused: models are refitted inside walk-forward validation, not saved
notebooks/      Unused so far
CLAUDE.md       Binding project rules
PROGRESS_LOG.md Dated record of all work and decisions
```

## Limitations

- **One monitor:** the U.S. Consulate Lahore monitor stands in for the whole city.
- **Preliminary data:** the PM2.5 data are preliminary.
- **Gaps:** AirNow's Data Management Center (email of 2026-10-23) confirmed that it received no data for 21 Oct – 7 Dec 2021 (cause unknown) and that 26 May – 29 Jun 2024 was partly unreceived and partly withheld after QA (unchanging values). The September 2022 gap was filled with AirNow's regenerated file (Stage 6). The 2021–22 and 2022–23 smog seasons remain under-represented.
- **Small sample:** 133 comparison weeks, 52 in the smog season.
- **ERA5 timing:** ERA5 for the previous week stands in for real-time weather analyses.
- **FIRMS:** cannot see fires under cloud.
- **HYSPLIT:** trajectories use coarse 2.5° meteorology.
- **Interpretation:** results are predictive associations only; nothing here establishes causes.

## Licence

Copyright © 2026 Sardar Zayaan Akhtar Nakai.

- **Code** (`src/`, `tests/`, `data/raw/hysplit/scripts/`): **MIT licence**, see [LICENSE](LICENSE).
- **Everything else made for this project** (figures, reports and tables in `results/`, the documentation, and the project's own derived data, including the HYSPLIT trajectories): **Creative Commons Attribution 4.0 International (CC BY 4.0)**, see [LICENSE-CC-BY-4.0.txt](LICENSE-CC-BY-4.0.txt).
- Both licences allow reuse, including modified versions, as long as the author is credited.
- **Third-party data are not covered.** Files in `data/processed/` and `results/` built from them stay subject to the terms under "Data sources and credits" above. In particular, AirNow-based data must always be labelled preliminary. The Natural Earth borders are public domain.
