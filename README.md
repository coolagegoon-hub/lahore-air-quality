# Lahore PM2.5 Air-Quality Forecasting

## Purpose

This research project investigates whether HYSPLIT trajectory clusters, ERA5 meteorology, NASA FIRMS fire activity, historical PM2.5, and simplified one-box mass-balance features improve forecasts of **weekly mean PM2.5** in Lahore, Pakistan. AQI may later be derived from observed or predicted PM2.5 once an applicable AQI standard is specified.

See [CLAUDE.md](CLAUDE.md) for the project's scientific, leakage, data, and integrity rules.

## Current status

**Stage 1 (PM2.5 data acquisition and QC) complete; weekly threshold and run rule pending.**
- The primary PM2.5 series is the AirNow rebuild for the U.S. Consulate Lahore monitor (AQS 586PK3010003). It is hourly, in PKT hour-ending time, covers 2019-05-22 → 2025-02-18, and has 1,777 days meeting the 18/24 rule.
- OpenAQ 8664 is kept for comparison only.
- AirNow data are preliminary.
- **No feature engineering or machine-learning model exists yet.**

See [PROGRESS_LOG.md](PROGRESS_LOG.md) and `results/tables/airnow_rebuild_report.md`.

## Folder structure

```
data/
  raw/          Original downloaded data (not tracked by Git; never edited by hand)
  processed/    Cleaned and quality-controlled data produced by code
notebooks/      Exploratory Jupyter notebooks
src/            Reusable Python modules for the pipeline
tests/          pytest tests
results/
  figures/      Generated figures
  tables/       Generated tables
models/         Saved model artifacts (not tracked by Git)
CLAUDE.md       Project rules and guidance
PROGRESS_LOG.md Record of completed and outstanding work
requirements.txt Python dependencies
```

## Installation

Requires Python 3.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Any credentials needed later (e.g. for data APIs) should be placed in a local `.env` file, which is excluded from version control.
