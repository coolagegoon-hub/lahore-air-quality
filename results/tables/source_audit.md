# Stage 1A — Historical PM2.5 Source Audit for Lahore

- **Audit date:** 2026-10-18
- **Scope:** Verify which publicly accessible historical PM2.5 sources can support the study. No full dataset was downloaded; no model was built; no packages were installed.
- **Method:** Direct HTTP requests (`curl`), the public OpenAQ Explorer web app (viewed in a browser), web pages read via fetch, and inspection of a small number of single-day/single-month sample files. Sample files were stored in a temporary scratch directory outside the project and are **not** part of this repository.

### Verification labels used below

| Label | Meaning |
|---|---|
| **VERIFIED** | Directly observed in this audit (HTTP response, file contents, or page content shown). |
| **PARTIAL** | Some aspects observed; others inferred or not checked. |
| **UNVERIFIED** | Reported by a secondary source (search result, article) or not tested. Do not rely on it. |
| **FAILED** | Tested and did not work. |

---

## Summary table

| Source | Accessible now? | PM2.5 conc. or AQI | Resolution | Lahore coverage demonstrated | Verdict |
|---|---|---|---|---|---|
| AirNow / US State Dept. archive (`dosairnowdata.org`) | **FAILED**: domain does not resolve | Both (raw conc. + NowCast + AQI) | Hourly | Only one archived month (Sept 2021, via Wayback Machine) | Best original format, but the official source is unreachable |
| OpenAQ AWS archive, location **8664** "US Diplomatic Post: Lahore" | **VERIFIED**: public, no key needed for S3 | Raw concentration (µg/m³) only | Hourly records in daily files | Daily files 2019-05-23 → 2025-03-04, but some contain only `-999` fill values | Best available, but **cross-check found discrepancies**; must be validated before use |
| OpenAQ API v3 | **VERIFIED** to require API key (HTTP 401) | Same data as archive (not tested) | — | Not tested | Usable with a free key; not tested |
| Punjab EPD daily AQI bulletins (`epd.punjab.gov.pk`) | **VERIFIED**: PDFs downloadable | Both for one station (24-h PM2.5 conc. + Pakistan AQI) | Daily (24-h), PDF only | One sampled bulletin; frequent station outages reported in it | Not suitable as the primary record; possible secondary/validation source |
| IQAir (`iqair.com`) | **PARTIAL**: page loads; no historical download found | Web history shows AQI (US); API: concentrations on paid tiers | Hourly display; API history 48 h max | None | Not suitable for multi-year history |

---

## 1. AirNow — U.S. Department of State Lahore monitor

### Access
- `https://dosairnowdata.org/dos/historical/Lahore/` — **FAILED**. `curl` returns *"Could not resolve host"*; `dig @1.1.1.1` returns `SERVFAIL`. WHOIS shows the domain is still registered (Amazon Registrar, expiry 2026-12-15), but its DNS does not resolve. Tested 2026-10-18.
- `https://www.airnow.gov/international/us-embassies-and-consulates/` — **FAILED** (HTTP 404). `https://www.airnow.gov/` returns HTTP 200.
- `https://gispub.epa.gov/airnowembassy/` — **PARTIAL**. The page loads and describes an "Archive" tab with daily values (24-h average for particle pollution) and a per-site "Historical" link. No direct file URLs were found in its content, and I did not use the interactive archive.
- Feed suspension — **UNVERIFIED (secondary source)**: an article by the Centre for Research on Energy and Clean Air (CREA) reports that AirNow stopped displaying embassy data on 4 March 2025, citing "funding constraints" (https://energyandcleanair.org/us-embassy-aq-data-halt/). This is consistent with OpenAQ's last Lahore file being dated 2025-03-04 (see §2).

### Archived sample (Wayback Machine)
- Wayback CDX query for prefix `dosairnowdata.org/dos/historical/Lahore/` returned **exactly one capture**:
  `https://web.archive.org/web/20210926135708id_/https://dosairnowdata.org/dos/historical/Lahore/2021/Lahore_PM2.5_2021_09_MTD.csv` (HTTP 200, 5,125 bytes). **VERIFIED.**
- Columns (**VERIFIED**): `Site, Parameter, Date (LT), Year, Month, Day, Hour, NowCast Conc., AQI, AQI Category, Raw Conc., Conc. Unit, Duration, QC Name`.
- Contents (**VERIFIED** for this file only):
  - Site `Lahore`; parameter `PM2.5 - Principal`; unit `UG/M3`; duration `1 Hr`; time zone labelled "LT" (local time).
  - 410 hourly rows, 2021-09-01 01:00 AM to 2021-09-26 12:00 AM.
  - QC flags: 408 `Valid`, 1 `Missing`, 1 `Invalid`. Missing values are coded `-999.0`.
  - **No rows at all for 2021-09-02 to 2021-09-08**, a 7-day gap.
  - Of the 19 days with any rows, 16 had ≥18 valid hours.
  - Some isolated very high hourly values are flagged `Valid`, e.g. 2021-09-15 05:00 = 390 and 07:00 = 449 µg/m³, next to neighbouring hours of about 94–169 µg/m³. These may be real spikes or instrument artefacts; they need QC review.
- Provides **both** raw hourly concentration and AQI (NowCast-based US AQI).
- Station coordinates: **not present** in the AirNow file. See §2 for the coordinates OpenAQ reports.
- Hour-ending vs hour-beginning timestamp convention: **UNVERIFIED** (not documented in the file).

### Assessment
This is the most informative format (raw concentration + QC flag + local time), but the official archive is **not reachable**, and only one month is recoverable from the Wayback Machine. Multi-year coverage from this source is **not demonstrated**.

---

## 2. OpenAQ — location 8664, "US Diplomatic Post: Lahore"

### Finding the location
- OpenAQ Explorer map (`https://explore.openaq.org/`), Lahore area, reference monitors only:
  - With "show locations with no recent updates" **off**: **no reference-grade monitors** displayed in Lahore. All active Lahore points are air sensors (low-cost). **VERIFIED** visually.
  - With that option **on**: one reference monitor, location **8664**. **VERIFIED.**
- Location page `https://explore.openaq.org/locations/8664` (**VERIFIED**, page text):
  - Name "US Diplomatic Post: Lahore"; type "Reference grade, Stationary".
  - Measures "PM2.5 µg/m³"; instrument "Government Monitor"; owner "Unknown Governmental Organization"; provider "StateAir Lahore".
  - "Reporting since 22/05/2019"; "Updated 2 years ago".
  - Chart times shown in Asia/Karachi (UTC+05:00).
  - Download via the Explorer requires sign-up/login.
- Coordinates (from the archive files, **VERIFIED**): lat **31.560078**, lon **74.33589**. Sensor ID **25135**.

### Access
- OpenAQ API v3 `https://api.openaq.org/v3/locations?...` — returns HTTP 401: *"A valid API key must be provided in the X-API-Key header."* **VERIFIED.** A free key requires an OpenAQ account; not obtained.
- Public AWS archive `https://openaq-data-archive.s3.amazonaws.com/` — anonymous listing and download work. **VERIFIED.** Path pattern (**VERIFIED**): `records/csv.gz/locationid=8664/year=YYYY/month=MM/location-8664-YYYYMMDD.csv.gz`.
- Archive documentation: https://docs.openaq.org/aws/about. It states files are written 72 h after the end of the day and "may be retroactively patched". It does not state whether values are validated, or the averaging-period timestamp convention.
- **License/terms for this location: UNVERIFIED.** No license is shown on the location page, and the archive docs page refers to a separate terms page that I did not review. Must be confirmed before publication.

### Coverage (daily file listing — metadata only, VERIFIED)
1,909 daily files, first **2019-05-23**, last **2025-03-04**.

| Year | Daily files present | Calendar days in range |
|---|---|---|
| 2019 | 223 | 223 (from 05-23) |
| 2020 | 363 | 366 |
| 2021 | 346 | 365 |
| 2022 | 241 | 365 |
| 2023 | 320 | 365 |
| 2024 | 353 | 366 |
| 2025 | 63 | 63 (to 03-04) |

Gaps of more than 14 days with no file: **2022-06-06 → 2022-09-22** (107 missing days) and **2023-02-23 → 2023-03-14** (18 missing days).

> **Important:** a daily file existing does **not** mean data exist. The file for **2021-09-05** contains 24 rows, all equal to `-999.0` (a missing-value code). The AirNow source has no rows for that day. Actual valid-hour coverage, and therefore the number of days meeting the ≥18/24 rule, is **not yet known**. Computing it requires downloading all ~1,900 files (small, about 0.25–0.35 kB each compressed), which was deferred to Stage 1B as instructed.

### Sample file format (VERIFIED: 2021-09-05, 2021-09-15, 2024-11-15)
- Columns: `location_id, sensors_id, location, datetime, lat, lon, parameter, units, value`.
- `parameter = pm25`; `units = µg/m³`; `datetime` in ISO-8601 with `+05:00` offset; 24 rows per day (01:00 … 00:00 of the next day).
- The format changes between years: the 2021 files are unquoted and the location is named `US Diplomatic Post: Lahore-8664`; the 2024 file quotes all fields and the location is named `Lahore-8664`. The parser must handle both.
- **No QC flag column.** Raw concentration only; no AQI.

### Cross-check against the original AirNow file (2021-09-15) — **discrepancy found**
I compared OpenAQ's 2021-09-15 hourly values with the Wayback-archived AirNow file for the same day:

- Both sources agree for 01:00–04:00 (43, 43, 39, 169).
- After that they diverge, in **12 of 24 hours**. OpenAQ is **missing** AirNow values 390 (05:00), 449 (07:00), 34 (14:00), one 35 (18:00) and 48 (21:00). Instead it **repeats** the preceding or following values (e.g. 141, 141; 57, 57; 62, 62). OpenAQ has 6 repeated consecutive values that day; AirNow has 2.
- The 2024-11-15 OpenAQ file showed no repeated consecutive values, but there is no AirNow file to compare it against.

**Interpretation (hypothesis, not established):** OpenAQ appears to have taken some 2021 hourly values from a "latest reading" feed, so some hours were missed and others duplicated. This means **OpenAQ 8664 cannot be assumed to be a faithful copy of the AirNow hourly record**, at least for 2021. The effect on daily means could be substantial on days with spikes: AirNow's 2021-09-15 includes 390 and 449, which OpenAQ omits.

---

## 3. Punjab Environment Protection Department (EPD)

### Access
- `https://epd.punjab.gov.pk/` — HTTP 200. **VERIFIED.**
- Daily bulletin sampled: `https://epd.punjab.gov.pk/system/files/20.01.2021.pdf` (HTTP 200, PDF). **VERIFIED**, contents read.
- Older bulletin: `https://epd.punjab.gov.pk/system/files/Ambient%20Air%20%20Quality.%2015-01-2018_0.pdf` — HTTP 200 (contents not read).
- `https://epd.punjab.gov.pk/aqi` — HTTP 200. Lists daily "AQI Report" PDFs. The fetched page showed only 3–23 December 2025 entries plus a date selector; some filenames contain mismatched dates (e.g. "23.11.2025" listed under 23 Dec). **PARTIAL**: the date selector was not used, and the full depth of the archive was not established.
- `https://aqms.punjab.gov.pk/` — **FAILED** (no response). Included only as a guessed URL; not claimed to exist.

### Content (from the 20.01.2021 bulletin, VERIFIED)
- Title: "Air Quality Index (AQI) recorded with AQMS of EPA in Lahore 20.01.2021 (based on previous 24 hours data)".
- Only **one PM2.5 station** in the table: **Met Station, Jail Road** (24-h PM2.5 = 18.996 µg/m³, AQI 54; PEQS value 35 µg/m³). Other stations report CO/NO2, or are listed as "not operational", "data not download due to expiry of internet package", or "AQMS not operational due to electricity shutdown".
- The AQI bands are from "Smog Policy 2017" (0–100 Good … 500+ Severe), a Pakistani/Punjab scale, **not** US EPA.
- The bulletin's US Embassy chart cites aqicn.org as its source, not an EPD measurement.
- No coordinates, no hourly data, no QC documentation, PDF only.

### Assessment
Useful as an independent **secondary** check for a single station, but daily-only PDFs, one PM2.5 station with documented outages, and no hourly QC make it unsuitable as the primary record. Multi-year continuity is **not demonstrated**.

---

## 4. IQAir

- `https://www.iqair.com/air-quality/pakistan/punjab/lahore` — page loads (a direct `curl` returned HTTP 429, rate-limited; the fetch tool succeeded). **PARTIAL.**
  - The historical graph shows **AQI (US) only**, hourly; no historical PM2.5 concentrations and no download option were found on the page.
  - The page lists "55 stations from 31 contributors", many of them low-cost sensors run by schools, companies and individuals.
- API page `https://www.iqair.com/commercial-air-quality-monitors/api` (**VERIFIED** page content): free Community plan = city-level AQI, no history; Startup = station-level concentrations, no history; Enterprise = "48h historical air quality & weather data". **No multi-year archive offered.**
- IQAir's separate "Historical Air Quality Data" product pages were **not reviewed** (UNVERIFIED).

### Assessment
Not suitable for a multi-year, documented historical PM2.5 concentration record.

---

## 5. Other candidates noted but not verified

- **Open Data Pakistan** spreadsheet, "Air Quality Index May 2019 – April 2020": `https://opendata.com.pk/dataset/air-quality-index-may-2019-april-2020/resource/decb72cb-1d47-4c2b-8414-33fb01f763d5`. Seen in search results only. Reported to cite aqicn.org. **UNVERIFIED.**
- **aqicn.org / WAQI** (`https://aqicn.org/city/pakistan/lahore/us-embassy/`): reports AQI, not raw concentration. **Not tested.**
- **GHDx (IHME) AirNow records:** exist for Colombo and Dhaka according to search results; no Lahore record found. **UNVERIFIED.**
- **Pakistan EPA (federal)** and **Urban Unit Punjab**: not investigated.

---

## Recommendation

**Primary candidate: OpenAQ location 8664 (US Diplomatic Post: Lahore), obtained from the public AWS archive.** This is the only verified, currently accessible source of **hourly PM2.5 concentrations (µg/m³) from a reference-grade monitor** in Lahore with a potential multi-year span (2019-05-23 → 2025-03-04). Access is anonymous and reproducible.

It should **not** be accepted as-is. Before modelling, Stage 1B should:

1. Download all 8664 daily files to `data/raw/` and record file listings and checksums.
2. Treat `-999` and any negative values as missing. Compute valid hours per day and apply the ≥18/24 rule to report the **actual** number of usable days, weeks and seasons.
3. Quantify duplicated consecutive values by year, which may indicate the ingestion artefact found in 2021.
4. Recover any further original AirNow files (e.g. other Wayback captures, or the EPA embassy map's "Historical" links, investigated manually) and extend the hour-by-hour cross-check beyond one day.
5. Confirm the OpenAQ data license and terms of use, and the hour-ending vs hour-beginning convention.

## Unresolved concerns

1. **Data fidelity:** a one-day comparison shows OpenAQ differs from the original AirNow hourly values in 12 of 24 hours. The extent across years is unknown.
2. **Record ends 2025-03-04,** apparently because the State Dept./AirNow feed was suspended (secondary source). No verified reference-grade replacement in Lahore after that date was found.
3. **Single station:** one monitor (31.5601 N, 74.3359 E) represents all of Lahore. Spatial representativeness is not established.
4. **Large gaps:** 2022-06-06 → 2022-09-22 has no files, and other missing periods are hidden behind `-999` files. These gaps will affect walk-forward validation folds and seasonal balance.
5. **QC information:** OpenAQ files lack the AirNow `QC Name` flag. Spikes flagged `Valid` in AirNow (e.g. 449 µg/m³) still need a documented QC rule.
6. **Official archive unreachable:** `dosairnowdata.org` does not resolve, so OpenAQ cannot be checked against the full original record.
7. **Pakistani official data:** Punjab EPD provides daily-only PDF bulletins with frequent outages. A machine-readable official historical archive was not found.
8. **AQI standard:** still undecided (US EPA vs Pakistan/Punjab "Smog Policy 2017" bands). This does not block Stage 1B, which uses concentrations.

No measurements in this document were invented. Every number above was read directly from a source response, sample file or page as described.
