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
| Weekly target | Monday–Sunday (PKT) mean, eligible with ≥ 6 of 7 valid days; 235 of 299 full weeks | `results/tables/stage2_weekly_target_report.md` |
| Baselines | Persistence, seasonal climatology, Ridge PM2.5-history model | same, §3 and §6 |
| Inputs | ERA5 weather, FIRMS fires, one-box mass balance, HYSPLIT trajectories (all from the week before the forecast) | `PROGRESS_LOG.md` |
| Main model | Walk-forward Random Forest, built up in 5 input layers | `results/tables/stage3_model_report.md`, `stage4_trajectory_report.md` |
| Explanation | Fold-by-fold out-of-sample SHAP, by input group | `results/tables/stage5_shap_report.md` |
| Figures | 9 figures (data, SHAP, results) | `results/figures/` |

**Main results** (133 eligible forecast weeks, 17 May 2021 – 10 Feb 2025, 52 of them Oct–Jan; mean absolute error in µg/m³):

- Persistence 36.4, seasonal climatology 33.7, Ridge PM2.5-history 30.5.
- Random Forest layers:
  - L1 (PM2.5 history) 30.2;
  - L2 (+ ERA5) 29.8;
  - L3 (+ fire) 29.4;
  - L4 (+ mass balance) 29.3;
  - L5 (+ HYSPLIT trajectories) 29.1.
- The full model beats persistence and climatology; 95% block-bootstrap intervals exclude zero.
- It does **not** reliably beat the Ridge PM2.5-history model.
- No added input layer gives a statistically reliable improvement. For example, trajectories (L5 vs L4): −0.2 µg/m³, 95% CI −1.2 to +1.0.
- All models under-predict the highest smog-season weeks.
- SHAP: the model relies mostly on recent PM2.5 (38%) and season (26%), then ERA5 weather (16%), mass balance (9%), fire (8%) and trajectories (4%). This describes model reliance, not causes.

Analysis designs for Stages 3b, 4 and 5 were written and committed **before** their results were computed (see the `*_predeclaration.md` files and the Git history).

**Not done / open:**
- trajectory-weighted fire exposure;
- association tests (H1–H3);
- a four-season scheme;
- embargo options (one week; per-source latency);
- the paper itself.

## Data sources and credits

| Data | Source | Notes |
|---|---|---|
| PM2.5 | U.S. Department of State monitor at the U.S. Consulate Lahore, via the **EPA AirNow** file archive | **Preliminary, not validated** (AirNow Data Exchange Guidelines). Credit the U.S. Department of State and the EPA AirNow program. |
| PM2.5 (comparison only) | OpenAQ location 8664 | Used only to diagnose data issues, never as model input |
| Weather | **ERA5** hourly time series on single levels, Copernicus Climate Change Service (C3S) Climate Data Store | Grid point 31.50 N, 74.25 E |
| Fires | **NASA FIRMS** VIIRS (Suomi NPP) standard-processing active fires | NOAA-20 used only as a cross-check |
| Trajectories | **NOAA ARL HYSPLIT** v5.4.2 driven by **NCEP/NCAR Reanalysis** 2.5° | 72 h back-trajectories, 06 UTC, 500 m AGL; coarse grid, so synoptic scale |
| Map borders | **Natural Earth** 1:10m (public domain) | Figure 3 only |

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
| `airnow_hourly_series` | The AirNow hourly archive: about 51 GB transferred, of which only the Lahore lines are kept (`src/airnow_bulk.py`) | `data/processed/airnow_586PK3010003_*.csv` |
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
- **Gaps:** long outages of unknown cause (e.g. 21 Oct – 7 Dec 2021). The 2021–22 and 2022–23 smog seasons are under-represented.
- **Small sample:** 133 comparison weeks, 52 in the smog season.
- **ERA5 timing:** ERA5 for the previous week stands in for real-time weather analyses.
- **FIRMS:** cannot see fires under cloud.
- **HYSPLIT:** trajectories use coarse 2.5° meteorology.
- **Interpretation:** results are predictive associations only; nothing here establishes causes.

## Licence

No licence has been chosen yet, so all rights are reserved by default. Choose one before making the repository public.
