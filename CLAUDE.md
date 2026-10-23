# CLAUDE.md — Lahore PM2.5 Forecasting Project

Guidance for Claude (and any contributor) working in this repository. These rules are binding.

## Scientific objective

Test whether the following inputs improve forecasts of PM2.5 in Lahore, Pakistan:

- HYSPLIT back-trajectory clusters
- ERA5 meteorology
- NASA FIRMS fire activity
- Historical PM2.5
- Simplified one-box mass-balance features

Improvement must be measured against baselines (e.g. persistence, climatology, and a PM2.5-history-only model) under the validation rules below.

## Primary forecast target

- **Target:** weekly mean PM2.5 (µg/m³).
- **AQI** is a derived quantity, computed from observed or predicted PM2.5 only after the applicable AQI standard (e.g. US EPA, Pakistan national, or other) has been explicitly specified and documented. **The AQI standard has not yet been chosen.** Do not compute or report AQI until it is.

## Development rules

- Write modular, reproducible Python. Reusable logic lives in `src/`; notebooks are for exploration and presentation only.
- Use vectorized pandas/NumPy operations where appropriate instead of row-wise Python loops.
- Fix and record random seeds where randomness is involved.
- Use **strict chronological walk-forward validation** for all forecast evaluation.
- **Never use random k-fold cross-validation** (or any shuffled split) for forecasting.

## Leakage rules

Never use:

- Future PM2.5 observations relative to the forecast issuance time.
- Target-derived features (any feature computed from the target being predicted).
- Information from overlapping target windows that leaks across evaluation boundaries (use gaps/embargoes between training and evaluation periods where windows overlap).
- Preprocessing (scalers, imputers, encoders, clustering, feature selection, etc.) fitted on the full dataset. Fit only on training data within each walk-forward fold.
- Observed target-week weather, trajectory, or satellite/fire data, unless that data was genuinely available at forecast issuance.

Forecast products (e.g. meteorological forecasts) may be used as inputs only when their issue times and availability are documented.

## Data rules

For every dataset and derived product, record:

- Units
- Time zones (Lahore local time is PKT, UTC+5; state explicitly which is used)
- Averaging periods
- Missingness
- Quality-control thresholds
- All transformations applied

**Daily PM2.5 completeness:** a daily mean requires at least 75% valid hourly observations (≥ 18 of 24 hours), unless the applicable monitoring protocol specifies otherwise — in which case document the protocol and threshold used.

Raw data in `data/raw/` is never edited by hand; all processing is done by code that writes to `data/processed/`.

**Primary PM2.5 series (decided 2026-10-18):** the AirNow rebuild for the U.S. Consulate Lahore monitor (AQS 586PK3010003), built by `src/airnow_hourly_series.py`:
- Hourly data: `data/processed/airnow_586PK3010003_hourly.csv`, PKT hour-ending.
- Daily data: `data/processed/airnow_586PK3010003_daily_18of24.csv`.
- Negative values are invalid.
- OpenAQ 8664 is kept only as a comparison source; do not use it as model input.
- AirNow data are preliminary and must be labelled as such, with credit to the U.S. Department of State and the EPA AirNow program.

**Data sources (decided 2026-10-20):**
- **PM2.5:** historical PM2.5 is the reference baseline. Always prefer locally measured or validated PM2.5 observations whenever they are available. The current series is a local reference-grade monitor (U.S. Consulate Lahore), but AirNow labels it preliminary, not validated. If a validated or QA'd local record becomes available, evaluate it as a replacement.
- **Weather:** ERA5 (Copernicus Climate Data Store).
- **Fire detections:** NASA FIRMS (VIIRS Suomi NPP standard processing; one sensor for the whole record; MODIS and VIIRS are never mixed).
- **Trajectories:** NOAA ARL HYSPLIT v5.4.2 back-trajectories driven by NCEP/NCAR Reanalysis 2.5° (72 h, 06 UTC, 500 m AGL). Clustering is fitted only inside each walk-forward training window.

**Repeated-value rule (decided 2026-10-20):** every hour of a run of ≥ 7 consecutive identical valid hourly values is invalid. This is applied before the 18/24 daily rule.

**Weekly target rule (decided 2026-10-20):** a Monday–Sunday (PKT) weekly mean is eligible only if ≥ 6 of its 7 days are valid daily means. The weekly mean is the mean of the valid days. A 6-day mean is not necessarily the true 7-day mean, so `complete_7_of_7` flags it.

## Interpretation rules

- Never present SHAP importance (or any feature-importance measure) as causal source attribution.
- Clearly distinguish **association**, **prediction**, and **causation** in all writing, figures, and results.

## Integrity rules

- Never fabricate data, URLs, API parameters, results, or test outcomes.
- Never claim something was run or tested unless it actually was.
- Never expose credentials. Keep secrets in a local `.env` file (git-ignored) and load them with `python-dotenv`; never hard-code them or print them.
