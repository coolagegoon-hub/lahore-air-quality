# Stage 6 — Backfilled September 2022 Data: Rerun Results (Before and After)

- **Date:** 2026-10-25
- **Design:** pre-declared in `stage6_backfill_predeclaration.md` (commit `c081b10`, before the record was rebuilt). Nothing else was changed.
- **Before:** results at commit `ee4366e`. **After:** this rerun.
- **Run:** all 12 pipeline steps in order, then `pytest` (128 passed). Wall-clock: about 7 minutes in total (Mac kept awake). The longer times in earlier log entries included sleep.
- **Data:** PM2.5 is AirNow (U.S. Department of State / EPA AirNow); the data are **preliminary**.

## 1. The backfill

| Check | Result |
|---|---|
| Backfill rows with QC "Valid" | 680 (3 "Missing" rows ignored) |
| Overlap with archive rows | 81 hours, all values identical |
| Hours added | 599 |
| Valid hours in the record | 43,151 → 43,750 |
| Complete days (≥ 18/24 h, after the run rule) | 1,776 → 1,801 |
| Eligible weeks (≥ 6/7 days) | 235 → 239 (223 with 7/7, 16 with 6/7) |
| Eligible weeks in 2022 | 29 → 33 |
| Eligible October–January weeks | 88 → 88 (September is outside that season) |
| Rebuild vs AirNow daily values | unchanged: 99.5% within 0.5 µg/m³ on 1,778 days |

## 2. Forecasts on the common set (MAE, µg/m³)

The common set grew from 133 weeks (52 in Oct–Jan) to **138 weeks (53 in Oct–Jan, 85 other months)**, same span 17 May 2021 – 10 Feb 2025.

| Method | Before | After | After, Oct–Jan | After, R² | After, bias |
|---|---|---|---|---|---|
| Persistence | 36.41 | 35.49 | 63.75 | 0.643 | +0.05 |
| Climatology | 33.67 | 32.58 | 54.83 | 0.732 | −11.06 |
| Ridge PM2.5-history | 30.52 | 29.67 | 54.08 | 0.766 | −4.65 |
| RF L1 history | 30.17 | 29.21 | 52.32 | 0.751 | −8.45 |
| RF L2 + ERA5 | 29.78 | 28.87 | 50.34 | 0.753 | −7.77 |
| RF L3 + fire | 29.42 | **28.13** | 50.11 | 0.753 | −7.67 |
| RF L4 + mass balance | 29.27 | 28.72 | 50.71 | 0.746 | −6.90 |
| **RF L5 + trajectories (primary)** | 29.07 | 28.35 | 50.37 | 0.756 | −6.18 |
| RF L1 + trajectories | 28.87 | 28.14 | 50.60 | 0.762 | −6.93 |
| RF L5, k = 4 / k = 8 | 29.49 / 28.90 | 28.30 / 28.15 | | | |
| RF on log PM2.5 (L4) | 29.61 | 28.87 | 52.29 | 0.744 | −7.72 |
| Ridge, all inputs (L4) | 34.25 | 32.71 | 56.83 | 0.688 | −0.94 |

## 3. Pre-declared comparisons (ΔMAE, 95% moving-block bootstrap CI, 4-week blocks unless stated)

| Comparison | Before (all weeks) | After (all weeks) | After (Oct–Jan) |
|---|---|---|---|
| L2 vs L1 (+ ERA5) | −0.39 (−2.31, +1.14) | −0.34 (−2.24, +1.31) | −1.98 (−5.80, +1.72) |
| **L3 vs L2 (+ fire)** | −0.36 (−1.55, +0.56) | **−0.74 (−1.90, −0.01)** | −0.24 (−1.77, +1.81) |
| L4 vs L3 (+ mass balance) | −0.15 (−1.02, +0.65) | +0.58 (−0.04, +1.22) | +0.60 (−0.96, +1.52) |
| **L5 vs L4 (primary)** | −0.20 (−1.22, +0.98) | −0.37 (−1.30, +0.77) | −0.34 (−2.80, +1.90) |
| L5 vs L4, 2-week blocks | −0.20 (−1.20, +0.90) | −0.37 (−1.46, +0.75) | |
| L5 vs L4, 8-week blocks | −0.20 (−1.07, +0.99) | −0.37 (−1.07, +0.56) | |
| L1 + traj vs L1 | −1.30 (−3.28, +0.67) | −1.07 (−2.78, +0.62) | −1.72 (−4.95, +2.48) |
| L5 vs Ridge history | −1.44 (−6.02, +1.74) | −1.33 (−5.40, +1.69) | −3.70 (−11.27, +3.55) |
| L5 vs climatology | −4.60 (−8.87, −1.53) | −4.23 (−8.23, −1.24) | −4.46 (−10.81, +1.03) |
| L5 vs persistence | −7.33 (−13.02, −2.38) | −7.14 (−12.71, −2.55) | −13.38 (−24.37, −3.71) |

## 4. SHAP (layer 5; 232 forecasts explained, 138 common weeks)

| Group | Share before | Share after | Oct–Jan after |
|---|---|---|---|
| PM2.5 history | 37.6% | 38.0% | 37.0% |
| Calendar (season) | 25.8% | 25.9% | 27.6% |
| ERA5 weather | 15.6% | 15.6% | 15.8% |
| Mass balance | 9.4% | 8.6% | 8.4% |
| Fire (FIRMS) | 8.0% | 8.3% | 6.2% |
| Trajectories | 3.6% | 3.7% | 4.9% |

Checks: reproduction error 5.0 × 10⁻⁷ (tolerance 10⁻⁶); additivity 4.3 × 10⁻¹³. Top non-history inputs unchanged: low-ventilation hours, boundary-layer height, surface pressure.

## 5. Reading

1. **Every error is a little lower** (0.3–1.2 µg/m³), mainly because five more weeks entered the common set. Rankings of the methods are unchanged, except that RF L3 now has the lowest overall MAE.
2. **The main conclusions hold:** the full model beats persistence and climatology, does not reliably beat the Ridge PM2.5-history model, and still under-predicts high smog weeks (Oct–Jan bias −23.9).
3. **One change:** adding fire features (L3 vs L2) now has an interval that narrowly excludes zero over all weeks (−0.74; −1.90 to −0.01). It does not hold in Oct–Jan, and the next layer (mass balance) raises MAE by a similar amount (+0.58; −0.04 to +1.22). With this many comparisons, one narrow interval is weak evidence. It is reported, not emphasised.
4. **Trajectories (primary comparison) still give no reliable gain:** −0.37 (−1.30, +0.77), with the same conclusion for 2- and 8-week blocks.
5. These are predictive comparisons only; nothing here shows causes.
