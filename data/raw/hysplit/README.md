# HYSPLIT back-trajectories for Lahore (U.S. Consulate PM2.5 monitor)

**STATUS: COMPLETE.** One 72 h back-trajectory per day, 2019-04-01 to 2025-02-28
(2,161 days). All days succeeded, and no days failed.

Produced 2026-10-21 to 2026-10-23 on a Windows 11 Pro laptop (10.0.26300, 64-bit),
Python 3.15.0, curl 8.21.0.

## What's in `hysplit_results.zip`

| File | Contents |
|---|---|
| `lahore_backtraj_endpoints.csv` | Every hourly endpoint of every trajectory: 157,753 rows (2,161 days × 73) |
| `failed_days.csv` | Days that failed or gave a short trajectory. Header only = none. |
| `manifest.csv` | The 72 meteorology files: name, URL, bytes, NOAA MD5, local MD5, SHA-256, status |
| `README.md` | This file |
| `hysplit_feasibility.md` | Phase 1 feasibility report and decisions |
| `remote_file_sizes.tsv` | Byte size of every candidate file, as reported by NOAA's server on 2026-10-21 |
| `scripts/download_met.py` | Resumable met download, verification against NOAA's MD5, manifest |
| `scripts/run_trajectories.py` | Writes CONTROL, runs `hyts_std`, converts tdump files to the CSV |

The 8.7 GB of meteorology files are **not** included. They are in `D:\hysplit_met\` on the
processing laptop, and `manifest.csv` identifies them exactly.

SHA-256 of `lahore_backtraj_endpoints.csv`:
`52bd34cf5b17c0acb050c4640aaa70cc529715a530f8c82429fc1aa1456482a8`

## Trajectory design

| Setting | Value |
|---|---|
| Receptor | 31.560078 N, 74.33589 E (U.S. Consulate Lahore PM2.5 monitor) |
| Arrival | 06:00 UTC each day (11:00 PKT), 500 m above ground level |
| Period | 2019-04-01 to 2025-02-28 (arrival dates), 2,161 trajectories |
| Duration | 72 h backward (`-72` in CONTROL) |
| Vertical motion | 0 = vertical velocity from the met data (tdump header: `OMEGA`) |
| Model top | 10,000 m AGL |
| Output interval | hourly, 73 endpoints per trajectory (hours 0–72) |
| Diagnostic output | pressure (`tm_pres = 1`, HYSPLIT default) |
| SETUP.CFG | none supplied: HYSPLIT defaults (effective values listed below) |
| Extra heights or times | none (decided 2026-10-21: 500 m and 06 UTC only) |
| Clustering | **none**. Do it later inside walk-forward validation to avoid leakage. |

Effective namelist written by HYSPLIT (`TRAJ.CFG`): `tratio=0.75, delt=0.0, mgmin=10,
khmax=9999, kmixd=0, kmsl=0, kagl=1, k10m=1, nstr=0, mhrs=9999, nver=0, tout=60,
tm_pres=1` (all other `tm_*` = 0), `dxf=1.00, dyf=1.00, dzf=0.01`.

Each run reads the arrival month's file, plus the previous month's file when the trajectory
starts in it (arrivals on days 1–3 of a month).

## Software

- **HYSPLIT v5.4.2**, Windows 64-bit. `MESSAGE` reports `HYSPLIT version: hysplit.v5.4.2`.
  - Source: `HYSPLIT_win64U_v5.4.2.zip` (491,835,610 bytes) from NOAA ARL's public download
    page <https://www.ready.noaa.gov/HYSPLIT_hytrial.php>.
  - SHA1 `a032db8bcffca2edd5a72eff05d5989f66bb1ffd`, which matches NOAA's published value.
    SHA-256 `f97df298a83d3995863f9c279481b107989cbf12d8ab0612b64c71a75c07385a`.
  - Unzipped to `C:\HYSPLIT`, with no installer and no admin rights. Program: `C:\HYSPLIT\exec\hyts_std.exe`.
  - `ASCDATA.CFG` was copied into the run folder with its data path changed from
    `'../bdyfiles/'` to `'C:\HYSPLIT\bdyfiles\'`, because the run folder is not under `C:\HYSPLIT`.

## Meteorology

- **NCEP/NCAR Reanalysis, 2.5° global, 6-hourly, ARL format** (`RPyyyymm.gbl`), from
  <https://www.ready.noaa.gov/data/archives/reanalysis/>.
- 72 monthly files, `RP201903.gbl` … `RP202502.gbl`, 8,705,115,904 bytes in total.
- **All 72 have `status = ok` in `manifest.csv`.** Each file's size equals the size NOAA's server
  reports, and its MD5 equals NOAA's published `listing.md5.txt`. A SHA-256 is recorded too.
- Provenance: 54 files were downloaded on this laptop. To finish in time, the months Jul 2021 –
  Jul 2022 and Apr 2024 – Feb 2025 were also downloaded from the same NOAA URL on a second laptop with
  the same script, then transferred as split zips. Each joined zip matched the second laptop's SHA-256,
  and every transferred file matched NOAA's MD5 before use. 18 files in the final set came from the
  second laptop (`RP202107`–`RP202207` and `RP202404`–`RP202408`). For `RP202409`–`RP202502`, this
  laptop's own downloads were used.
- HYSPLIT warns `FLUXES not found in data` and switches to `KBLS=2`, which estimates stability from
  wind and temperature profiles. This is expected for this dataset, which has no surface flux fields.
- Limitation for the methods section: 2.5° is coarse near the Himalaya and Sulaiman ranges and for a
  500 m arrival height. Treat the trajectories as synoptic-scale transport.

## CSV columns (`lahore_backtraj_endpoints.csv`)

| Column | Meaning |
|---|---|
| `arrival_time_utc` | Trajectory arrival time at Lahore (ISO 8601, UTC). This is the trajectory's ID. |
| `arrival_height_m_agl` | Arrival height (always 500.0) |
| `hour_back` | Hours before arrival, 0–72 |
| `point_time_utc` | Time of this endpoint (UTC) |
| `lat`, `lon` | Endpoint position, degrees (3 decimals, as written by HYSPLIT) |
| `height_m_agl` | Endpoint height, m above ground |
| `pressure_hpa` | Pressure at the endpoint, hPa |

Checks on the final CSV:
- 2,161 trajectories (every day 2019-04-01 to 2025-02-28), 157,753 rows, exactly 73 points each,
  with `hour_back` 0–72 present. No empty pressure values.
- Pressure 236.7–1012.2 hPa; height 0.0–9,747.1 m; lat 12.056–65.672; lon −27.919–96.032.
- 2,828 endpoints have `height_m_agl = 0.0`: the trajectory touched the ground, where HYSPLIT keeps
  it at the surface. These are model output, not missing values.

## Failed days

**None.** `failed_days.csv` contains only its header. Every one of the 2,161 runs produced a full
73-point trajectory.

## Commands run

```bat
REM met download (resumable; re-running skips verified files). Run on this laptop as split
REM month ranges in parallel (max 2 connections to NOAA), with the same script on the second laptop.
python -I scripts\download_met.py --dest D:\hysplit_met --first 2019-03 --last 2025-02

REM trajectories + CSV (re-running skips days whose tdump already exists)
python -I scripts\run_trajectories.py --hyts C:\HYSPLIT\exec\hyts_std.exe ^
    --met D:\hysplit_met --runs D:\hysplit_met\_runs ^
    --out lahore_backtraj_endpoints.csv --start 2019-04-01 --end 2025-02-28
```

The raw `tdump` files (2,161) are kept in `D:\hysplit_met\_runs\tdump\` on the processing laptop.
