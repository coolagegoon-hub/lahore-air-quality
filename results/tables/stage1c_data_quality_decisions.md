# Stage 1C — Data-Quality Decisions for Lahore PM2.5 (OpenAQ 8664 / AirNow 586PK3010003)

> **Status update (2026-10-23):** All §7 decisions are made: (1) primary source = AirNow archive rebuild (option b); (2) run rule = runs of ≥ 7 h invalid; (3) weekly threshold = ≥ 6 of 7 valid days; (4) OpenAQ is used only for diagnostics, never as model input; (5) location 6506 remains unresolved and is not used. An email asking AirNow about the causes of the long outages was sent 2026-10-23; no reply yet.

- **Date:** 2026-10-18
- **Code:**
  - `src/stage1c_analysis.py` (new)
  - `src/airnow_archive.py` (new)
  - `src/pm25_qc.py` (unchanged)
  - Tests: `tests/test_stage1c.py` (new), `tests/test_pm25_qc.py` (unchanged)
- **Outputs:** `results/tables/stage1c/*.csv|json`, `data/processed/airnow_586PK3010003_daily.csv`
- **Reproduce** (AirNow lines are cached under `data/raw/airnow_files/`):
  ```bash
  .venv/bin/python -m src.stage1c_analysis
  .venv/bin/python -m pytest -q tests
  ```
- **Scope:**
  - No model was built.
  - No ERA5, HYSPLIT or FIRMS data were touched.
  - No observation was deleted; the original OpenAQ raw files are unchanged.
  - Exclusion rules are applied only to copies, in named sensitivity scenarios.
  - **No threshold or source has been selected**; the decisions are listed in §7.

### Evidence labels

| Label | Meaning |
|---|---|
| **[ORIGINAL]** | Supported by comparison with original AirNow archive files. |
| **[DOC]** | Stated in official documentation (quoted or cited). |
| **[FILE]** | Read directly from the downloaded data files. |
| **[HEURISTIC]** | Pattern-based check only; no original-source confirmation. |
| **[UNRESOLVED]** | Could not be determined. |

### Original-source data obtained in this stage

The public AirNow file archive `https://s3-us-west-1.amazonaws.com/files.airnowtech.org/airnow/YYYY/YYYYMMDD/` (listing page `https://files.airnowtech.org/`) contains every AirNow site, including State Department posts. For Lahore, AQS ID **586PK3010003**, only the matching lines were kept:

- **Daily:** `daily_data_v2.dat` for every day from 2019-05-22 to 2025-03-06 (2,116 files, none missing). It holds 1,778 Lahore `PM2.5-24hr` values, from 2019-05-22 to 2025-02-17.
- **Hourly:** `HourlyData_YYYYMMDDhh.dat` for 18 eight-day windows (3,456 hours): 17 seasonal sample weeks from 2019-07 to 2025-01 (no 2022-07 window), plus 2024-05-30 to 06-06 around the stuck value.
- These AirNow products are near-real-time data. AirNow describes them as "not fully verified or validated … preliminary" [DOC: AirNow Hourly Data File fact sheet, updated Aug 2025].

---

## 1. Timestamp convention

### Facts

| Item | Evidence | Label |
|---|---|---|
| OpenAQ files: `datetime` is ISO-8601 with `+05:00`; each daily file runs 01:00 → 00:00 (next day) | Stage 1B, all 1,909 files | [FILE] |
| OpenAQ: "Data on OpenAQ are harmonized to follow an exclusive time-ending standard… 03:00 represents the data from 02:00 until 02:59" | https://docs.openaq.org/using-the-api/dates-datetimes | [DOC] |
| OpenAQ daily aggregates are "computed from the hourly average values from 01:00 to 0:00 in local time" | https://docs.openaq.org/resources/measurements | [DOC] |
| AirNow hourly files: time is GMT and "corresponds to the beginning of the measurement period" | AirNow Hourly Data File fact sheet (https://docs.airnowapi.org/docs/HourlyDataFactSheet.pdf, updated Aug 2025) | [DOC] |
| AirNow daily values: "midnight-to-midnight, begin-hour, and Local Standard Time" | AirNow Daily Data File fact sheet (https://files.airnowtech.org/airnow/docs/DailyDataFactSheet.pdf, updated Aug 2025) | [DOC] |
| AirNow site metadata gives Lahore GMT offset **+5.00** | `monitoring_site_locations.dat`, 2021-09-15 | [FILE] |
| The State Dept. CSV label "2021-09-15 01:00 AM" = 43 equals AirNow begin-hour 19:00 GMT on 09-14 (00:00–00:59 PKT, i.e. hour-**ending** 01:00 PKT) | 2021-09-15, all 24 hours | [ORIGINAL] |

### Is the current QC day assignment correct?

`src/pm25_qc.py` treats each timestamp as hour-ending and assigns 00:00 to the preceding day. A day therefore covers hour-ending 01:00 … 00:00, i.e. begin-hours 00:00 … 23:00 PKT. This **matches** both:
- OpenAQ's documented convention and its daily aggregation; and
- AirNow's own daily definition (midnight-to-midnight, begin-hour, local standard time; PKT has no DST).

The rule is correct **for timestamps that really are hour-ending**.

### Problem found: OpenAQ's labels are not consistently aligned with the original [ORIGINAL]

AirNow's documented begin-hour GMT times were converted to hour-ending PKT, and the share of hours where OpenAQ equals AirNow (±0.15 µg/m³) was counted with AirNow shifted by k hours. Here k = +1 means OpenAQ(t) equals AirNow's hour-ending t+1, i.e. OpenAQ is labelled one hour early (as hour-beginning). Source: `airnow_lag_alignment_by_window.csv`.

| Window (8 days) | k = 0 | k = +1 | Interpretation |
|---|---|---|---|
| 2019-07 | **100.0** | 1.6 | aligned (hour-ending correct) |
| 2019-11 | 51.6 | 48.7 | **mixed** |
| 2020-01 | 37.0 | 63.9 | **mixed** |
| 2020-07 | 51.4 | 59.2 | **mixed** |
| 2020-11 | 32.8 | 68.1 | **mixed** |
| 2021-01 | 64.1 | 37.7 | **mixed** |
| 2021-07 | 47.7 | 58.6 | **mixed** |
| 2022-01 | **97.9** | 4.2 | aligned |
| 2022-11 | **100.0** | 0.0 | aligned (only 20 OpenAQ hours) |
| 2023-01 | **98.9** | 3.4 | aligned |
| 2023-07 | 1.9 | **96.2** | **shifted: OpenAQ labels = hour-beginning** |
| 2023-11 | 0.5 | **100.0** | **shifted** |
| 2024-01 | 2.1 | **100.0** | **shifted** |
| 2024-07 | **95.8** | 5.8 | aligned |
| 2024-11 | **96.3** | 5.3 | aligned |
| 2025-01 | **100.0** | 1.6 | aligned |

(2021-11 and 2024-05/06: neither source has overlapping valid hours.)

**Basis for the decision:**
1. The fixed hour-ending rule is right in principle, and right wherever OpenAQ is aligned.
2. In at least 2023-07 → 2024-01, OpenAQ timestamps are **one hour early relative to AirNow's documented convention**, contrary to OpenAQ's stated time-ending standard. Applying the rule there assigns one hour per day to the wrong day.
3. In 2019-11 → 2021-07, OpenAQ is **inconsistently** aligned: some hours carry AirNow's value for that hour, others the next hour's.
4. The exact dates where alignment changes are **[UNRESOLVED]**, because only sample weeks were compared.

**Effect on daily means:**
- Complete-day OpenAQ means vs AirNow's own daily values: Pearson r = 0.997–0.9995 every year, mean difference between −0.30 and +0.52 µg/m³ (`airnow_daily_comparison_by_year.csv`). The timing problem therefore has only a small effect on daily and weekly means.
- It does matter for hourly features, including the 18/24 completeness counts.

---

## 2. Repeated values

### Inventory [FILE]
`repeat_runs_all.csv` lists every run of ≥ 2 consecutive identical valid hourly values: **3,203 runs**, with first/last hour-ending timestamp, first-hour start, length, value and days. Lengths by year (`repeat_run_length_by_year.csv`):

| Year | 2 h | 3 h | 4–5 h | 6 h | 7 h | > 24 h |
|---|---|---|---|---|---|---|
| 2019 | 106 | 0 | 0 | 0 | 0 | 0 |
| 2020 | 1,143 | 59 | 7 | 1 | 0 | 0 |
| 2021 | 839 | 48 | 8 | 0 | 0 | 0 |
| 2022 | 113 | 4 | 0 | 0 | 0 | 0 |
| 2023 | 387 | 14 | 0 | 0 | 0 | 0 |
| 2024 | 411 | 32 | 5 | 0 | 1 | 1 |
| 2025 | 24 | 0 | 0 | 0 | 0 | 0 |

There are only three runs of ≥ 6 h (`long_run_daily_impacts.csv`):

| Run (hour-ending, PKT) | Length | Value | Days affected | Evidence |
|---|---|---|---|---|
| 2020-08-12 03:00 → 08:00 | 6 h | 26.0 | 2020-08-12: S0 mean 31.46 (24 valid h); S6 33.28 (18 valid h); S7 unchanged | **[HEURISTIC]**: outside the AirNow windows |
| 2024-05-31 07:00 → 13:00 | 7 h | 67.0 | 2024-05-31 | **[ORIGINAL]** |
| 2024-05-31 15:00 → 2024-06-05 14:00 | 120 h | 67.0 | 2024-05-31 … 06-05; S0 makes 05-31 to 06-04 "complete" with mean exactly 67.0 | **[ORIGINAL]** |

### The 120-hour run [ORIGINAL]
- All 192 AirNow hourly files for GMT 2024-05-30 → 06-06 contain **no Lahore record**.
- The same ID (586PK3010003) is present on 2024-05-20 and 2024-11-15; it is absent on 2024-05-31 12 GMT (Islamabad and Peshawar reporting) and 2024-06-20 12 GMT (Islamabad and Karachi reporting).
- AirNow has **no daily value** for 2024-05-31 … 06-04.
- **Conclusion:** the 67.0 µg/m³ values (both 2024 runs, 127 hours) are not in the original source and are not measurements.

### High repeat rates in 2020–2021 [ORIGINAL]
- In the comparison windows, OpenAQ's repeat rate far exceeds AirNow's: 2020-11 18.2% vs 1.0%; 2021-01 18.2% vs 1.6%; 2020-07 30.4% vs 9.4%; 2021-07 17.0% vs 5.4%.
- Of the 191 OpenAQ runs fully inside the AirNow windows, only **22** also occur in AirNow (`repeat_runs_vs_airnow_by_window.csv`). None of the 34 runs in 2020-11, and none of the 34 runs in 2021-01, exist in the original.
- **Mechanism:** in "mixed" windows, almost every OpenAQ value that differs from AirNow equals AirNow's **next-hour** value (e.g. 2020-11: 128 of 129; 2021-01: 69 of 69). When OpenAQ switches from aligned to one-hour-early, one AirNow value is skipped. When it switches back, a value appears twice. This produces both the extra repeats and the missing peaks seen in Stage 1A (the 390 and 449 µg/m³ hours).
- **Not explained:** the cause on OpenAQ's side (e.g. ingestion timing). [UNRESOLVED]

### Short runs outside the windows [HEURISTIC]
Most 2–5 h runs elsewhere in 2020–2021 are probably the same artefact. Some are genuine: AirNow itself repeats 0.5–9.4% of hours, because many values are whole numbers. **Run length alone cannot separate genuine from artefactual short runs.**

### Sensitivity results (`scenario_summary.csv`; nothing deleted)

| Scenario | Hours excluded | Valid hours | Complete days (≥18/24) | Days lost vs S0 | Complete days with changed mean | Max daily-mean change |
|---|---|---|---|---|---|---|
| S0 unflagged | 0 | 36,409 | 1,464 | — | — | — |
| S6 runs ≥ 6 h | 133 | 36,276 | 1,459 | 5 (2024-05-31 … 06-04) | 1 (2020-08-12) | 1.82 µg/m³ |
| S7 runs ≥ 7 h | 127 | 36,282 | 1,459 | 5 (same) | 0 | 0 |

- **Weekly counts are identical across all three scenarios** (§3). The affected 2024 weeks fall below 5/7 in every scenario.
- **Daily comparison with AirNow by scenario:** S0 contains 5 complete days with no AirNow value (the stuck days). S6 and S7 contain none. Other agreement statistics are unchanged.
- **Neither S6 nor S7 removes the 2020–2021 artefact.** It consists of short runs and shifted labels, not long runs.

---

## 3. Weekly target completeness

**Definitions:**
- Weeks run Monday–Sunday, PKT; only full weeks inside the record are counted.
- A valid day is a daily mean meeting the ≥ 18/24 rule.
- Year and smog season (October–January) are assigned by each week's Thursday.
- Counts are identical in S0, S6 and S7 (`weekly_threshold_counts_by_year.csv`, `…_by_smog_season.csv`).

### By year

| Year | Full weeks | 7/7 | ≥ 6/7 | ≥ 5/7 |
|---|---|---|---|---|
| 2019 (from May) | 31 | 22 | 28 | 29 |
| 2020 | 53 | 34 | 43 | 48 |
| 2021 | 52 | 15 | 22 | 27 |
| 2022 | 52 | 3 | 7 | 13 |
| 2023 | 52 | 32 | 36 | 40 |
| 2024 | 52 | 33 | 35 | 36 |
| 2025 (to Feb) | 9 | 6 | 7 | 7 |
| **Total** | **301** | **145** | **178** | **200** |

### By smog season (October–January)

| Season | Full weeks | 7/7 | ≥ 6/7 | ≥ 5/7 |
|---|---|---|---|---|
| 2019-20 | 18 | 14 | 16 | 16 |
| 2020-21 | 18 | 12 | 15 | 17 |
| 2021-22 | 17 | 7 | 8 | 8 |
| 2022-23 | 17 | 0 | 2 | 4 |
| 2023-24 | 17 | 16 | 16 | 16 |
| 2024-25 | 18 | 17 | 18 | 18 |
| **Total** | **105** | **66** | **75** | **79** |

### How missing days affect a weekly mean
A weekly mean from fewer than 7 days is the mean of the available days, so it estimates the true weekly mean with extra error.

To size this error, every one of the 7/7 weeks had every possible 1-day and 2-day subset removed (7 and 21 subsets per week; no randomness). Results are from `weekly_missing_day_error.csv`, S0:

| Days missing | Season | Weeks | Mean abs. error | Median abs. % error | 95th pct % error | Max % error |
|---|---|---|---|---|---|---|
| 1 | non-smog | 79 | 2.83 µg/m³ | 2.97% | 10.33% | 27.83% |
| 1 | smog | 66 | 7.93 µg/m³ | 2.83% | 10.15% | 22.87% |
| 2 | non-smog | 79 | 4.44 µg/m³ | 4.94% | 16.47% | 43.05% |
| 2 | smog | 66 | 12.00 µg/m³ | 4.14% | 16.26% | 37.12% |

### Trade-offs (no threshold selected)
- **7/7:** weekly means are exact. However, only 145 weeks remain, including 0 in the 2022-23 smog season and 3 in all of 2022.
- **≥ 6/7:** adds 33 weeks. Typical error is about 3%, but about 1 in 20 such weeks is off by more than 10%.
- **≥ 5/7:** adds 55 weeks over 7/7. Typical error is about 4–5%, with a 95th percentile near 16%.
- **What this experiment assumes:** missing days are a random subset of the week. Real outages may cluster around particular conditions (e.g. power or instrument failures during extreme smog), so the true error may be larger. **This has not been tested.**
- **In absolute terms,** the error is largest in the smog season, because concentrations are highest then.
- **Alternatives to consider:** use a weekly-coverage weight, or keep the count of valid days as a feature or quality flag.

---

## 4. Station identity

### Location 8664 — exact metadata

| Field | Value | Source | Label |
|---|---|---|---|
| OpenAQ location ID | 8664 | archive path; Explorer `/locations/8664` | [FILE]/[DOC] |
| Name | "US Diplomatic Post: Lahore" (Explorer); `US Diplomatic Post: Lahore-8664` (30,648 rows) and `Lahore-8664` (13,868 rows) in files | Explorer page; files | [FILE] |
| Sensor ID | 25135 (only one) | files | [FILE] |
| Parameter / units | `pm25` / `µg/m³` (only values) | files | [FILE] |
| Coordinates | 31.560078, 74.33589 (every row) | files | [FILE] |
| Time zone | timestamps `+05:00`; Explorer charts "Asia/Karachi (UTC+05:00)" | files; Explorer | [FILE] |
| Type / instrument | "Reference grade, Stationary"; instrument "Government Monitor"; owner "Unknown Governmental Organization" | Explorer page (Stage 1A) | [DOC] |
| Provider | "StateAir Lahore" | Explorer page | [DOC] |
| Reporting since | "22/05/2019" (Explorer); first file 2019-05-23 | Explorer; files | [DOC]/[FILE] |
| Licence shown | none on the Explorer page | Explorer page | [UNRESOLVED] |

### Correspondence with the AirNow / State Department monitor
AirNow `monitoring_site_locations.dat` (2021-09-15) contains the record `586PK3010003|PM2.5|3010|Lahore|Active|PK3|U.S. Department of State Pakistan - Lahore|DSPK|31.560078|74.335890|…|5.00|PK…`.

Evidence that 8664 is this monitor:
- identical coordinates;
- AirNow daily values start 2019-05-22, the same as OpenAQ's "reporting since";
- of 2,553 overlapping hourly pairs, 2,546 (99.7%) match AirNow at the same, next or previous hour (±0.15 µg/m³): 1,549 at the same hour and 997 only at the next hour (§1);
- daily means correlate at r ≥ 0.997.

**This identity is supported by original-source comparison.**

The measurement method (e.g. instrument model) is **[UNRESOLVED]**: neither OpenAQ nor the AirNow files state it.

### Location 6506 — **[UNRESOLVED]**
- `https://explore.openaq.org/locations/6506` returns "We can't find the page you've requested".
- `openaq-data-archive` has **no objects** under `records/csv.gz/locationid=6506/` or `records/parquet/locationid=6506/`.
- The Wayback Machine has no captures of `api.openaq.org/v2/locations/6506` or `explore.openaq.org/locations/6506`.
- The OpenAQ v3 API requires a key (HTTP 401 without one), and none was used.
- The relationship between 6506 and 8664 therefore cannot be established. It could be an older or retired OpenAQ ID for the same post, but that is an **assumption**.
- To resolve it: one call to `GET https://api.openaq.org/v3/locations/6506` with a registered key, which you would have to set up yourself.

---

## 5. Data terms and current coverage

### Terms
**OpenAQ platform terms** (https://docs.openaq.org/about/terms, no date shown):
- "Attribution to OpenAQ as the source data is also required when using OpenAQ services for accessing the data."
- "When required, OpenAQ users must acknowledge the original source(s) of any data they use."
- Data are "offered as-is, without warranty of any kind".
- **Compliance concern:** "downloading data is strictly prohibited unless done through registered and authorized use". The anonymous S3 download used in Stage 1B is documented by OpenAQ (`docs.openaq.org/aws/about`). The Registry of Open Data on AWS (https://registry.opendata.aws/openaq/) lists it as "Managed By: OpenAQ", "License: Varies, depends on data provider". The terms do not say whether anonymous S3 access counts as "authorized use". **[UNRESOLVED]**: register an account and/or confirm with OpenAQ before publication.

**AirNow Data Exchange Guidelines** (https://docs.airnowapi.org/docs/DataUseGuidelines.pdf, updated Aug 2025). This is the source-provider route for the State Department data:
- Data "are not fully verified or validated … should be considered preliminary"; they "should not be used to formulate or support regulation, **ascertain trends**…".
- "Credit should first be given to the appropriate source … and the EPA AirNow program."
- Analyses "must indicate that these data are preliminary".
- "Publications, analyses … that rely on these data must be made known to the relevant … agencies and the EPA AirNow program."
- The form asks users to agree and return it to dmc@airnowtech.org. **That agreement form has not been sent, and nothing was sent anywhere.**
- **Implication for this project:** forecasting is the stated purpose of AirNow data. However, any trend statements must be avoided or caveated, results must be labelled preliminary, and the U.S. Department of State, the EPA AirNow program and OpenAQ must be credited.
- State Department-specific terms beyond the AirNow guidelines: **[UNRESOLVED]** (not found).

### Last observation [FILE]/[ORIGINAL]
- **OpenAQ 8664:** last row 2025-03-04 17:00 (`-999`); **last valid value 2025-02-18 18:00 PKT** (hour-ending).
- **AirNow daily:** last Lahore `PM2.5-24hr` is **2025-02-17**.
- **After that** [HEURISTIC]: one AirNow hourly file per month (the 15th, 06 GMT) from 2025-03-15 to 2026-10-15 contained **no Lahore record**. Islamabad appears until 2026-02-15, Peshawar only on 2025-03-15. The current `today/` file (2026-10-18 09 GMT) has no Pakistan record. This is one hour per month, not an exhaustive search.

### Retrospective vs live use
- The record covers **2019-05-22 → 2025-02-18**, and the monitor has not reported since.
- **This dataset supports retrospective (hindcast) evaluation only.**
- A live forecasting system would need a **separate, currently reporting** Lahore PM2.5 source, plus a demonstrated overlap period showing it is consistent with this monitor (bias and scale). Without that, a model trained on this record cannot be assumed to transfer.
- No such source has been verified:
  - Punjab EPD publishes daily PDF bulletins (Stage 1A);
  - OpenAQ shows active low-cost sensors in Lahore, but none was evaluated.

---

## 6. Additional finding: AirNow has coverage OpenAQ lacks

| Smog season | AirNow daily values | OpenAQ complete days |
|---|---|---|
| 2019-20 | 121 | 114 |
| 2020-21 | 121 | 113 |
| 2021-22 | 72 | 70 |
| **2022-23** | **97** | **37** |
| 2023-24 | 120 | 117 |
| 2024-25 | 122 | 122 |

- **Daily:** over the whole record AirNow has 1,778 daily values vs 1,464 OpenAQ complete days. On 318 days AirNow has a daily value but OpenAQ is incomplete.
- **Hourly:** in the sample windows AirNow has hours OpenAQ lacks, e.g. 171 of 192 hours in 2022-11 and 102 in 2023-01.
- **Caveat:** AirNow's daily completeness criterion is **[UNRESOLVED]**: it was not found in the fact sheets, so it cannot yet be confirmed to meet the 18/24 rule.

---

## 7. Decisions needed (nothing chosen)

1. **Primary hourly source.** Options:
   - **(a)** keep OpenAQ 8664 and accept the label misalignment and artefacts described above;
   - **(b)** rebuild the hourly record from the AirNow archive (documented time convention, original values, more coverage). This would mean streaming about 50,700 hourly files. That is an estimated ~65 GB of transfer at ~1.28 MB per file, keeping only the Lahore lines;
   - **(c)** use AirNow `PM2.5-24hr` daily values directly, once AirNow's daily completeness rule is documented.
2. **Run exclusion rule.** S6 vs S7 differ only on 2020-08-12 (heuristic only). Both remove the 2024 run, which is confirmed against the original. Neither fixes the 2020–2021 artefact.
3. **Weekly threshold:** 7/7, ≥ 6/7 or ≥ 5/7 (§3).
4. **Terms:** register for OpenAQ access and decide whether to submit the AirNow guidelines form; both are your actions.
5. **Location 6506:** resolve with an API key, or drop it.

## 8. Tests performed
- `.venv/bin/python -m pytest -q tests` → **16 passed**: 9 existing in `test_pm25_qc.py` and 7 new in `test_stage1c.py`.
- The new tests cover:
  - run detection, lengths and times;
  - whole-run exclusion at the threshold, with the input left unchanged;
  - Thursday-based week year and season, and dropping partial weeks;
  - threshold counts;
  - the exhaustive missing-day error (including a known 50% case);
  - detection of a one-hour lag;
  - AirNow begin-hour GMT → hour-ending PKT conversion and caching, with the network mocked.
- All tests use synthetic data. The real-data results above come from running `src.stage1c_analysis`; they are not unit-tested.
