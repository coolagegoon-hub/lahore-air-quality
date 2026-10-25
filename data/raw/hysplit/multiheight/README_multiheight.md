# Lahore back-trajectories at 100 m and 250 m arrival height

Run on 2026-10-25 (15:49–15:56 PKT, 6.3 min) on the same Windows 11 laptop and with the same
installation as the original 500 m run. Nothing new was downloaded, and no setting changed
except the arrival height.

## Purpose
This tests whether the 500 m trajectories sit above Lahore's shallow surface smog layer. At the
06 UTC arrival time, the boundary layer is below 500 m on most winter days.

## Software, data and settings
- **HYSPLIT version: `hysplit.v5.4.2`** (from `MESSAGE`); program `C:\HYSPLIT\exec\hyts_std.exe`.
- Meteorology: NCEP/NCAR Reanalysis 2.5°, ARL format, `D:\hysplit_met\RP201903.gbl` … `RP202502.gbl`.
  These are the same 72 files as the original run, all `status = ok` (NOAA MD5) in `D:\hysplit_met\manifest.csv`.
- Receptor 31.560078 N, 74.33589 E (U.S. Consulate Lahore PM2.5 monitor).
- Arrival **06 UTC** (11:00 PKT), heights **100 m and 250 m AGL**, days 2019-04-01 to 2025-02-28.
- 72 h backward, vertical motion 0 (met-model vertical velocity), model top 10,000 m. These are
  `run_trajectories.py` defaults and were unchanged. The script itself was not edited (SHA-256
  `f5a3ff460ecd989a62fc3d6fc1a0280d9fa6b7c6bcd923e97f2e255762f0bb39`).
- No SETUP.CFG, so HYSPLIT defaults apply, identical to the original run.

## Exact command (run from the project's `hysplit_lahore` folder)
```
python -I scripts\run_trajectories.py --hyts C:\HYSPLIT\exec\hyts_std.exe --met D:\hysplit_met --runs D:\hysplit_met\_runs --out D:\hysplit_multi\lahore_backtraj_multiheight_endpoints.csv --start 2019-04-01 --end 2025-02-28 --hour 6 --height 100 250
```

## Result
```
runs requested: 4322, endpoint rows: 315506, problems: 0
```
- `failed_days.csv` contains only its header, so **0 problems**.
- `lahore_backtraj_multiheight_endpoints.csv`: 24,579,488 bytes, SHA-256
  **`679683366ae21ef5e078f89aac2217d0b025c0e2d53c1bd50bc0173224571ebb`**.
- Checks run:
  - 4,322 (arrival_time_utc, arrival_height_m_agl) pairs, each with exactly 73 rows (hour_back 0–72).
  - Arrival heights are only 100.0 and 250.0, and the arrival hour is always 06.
  - 2,161 days, 2019-04-01 to 2025-02-28. No empty pressure values.
  - 100 m: 157,753 rows, pressure 236.5–1014.2 hPa, 6,349 endpoints at ground level (0.0 m).
  - 250 m: 157,753 rows, pressure 236.4–1019.5 hPa, 4,581 endpoints at ground level.
  - Ground-level points are model output (trajectory touched the surface), not missing values.
- Columns are the same as the original CSV: `arrival_time_utc, arrival_height_m_agl, hour_back,
  point_time_utc, lat, lon, height_m_agl, pressure_hpa`.

## Warnings (same as the original 500 m run, expected for this dataset)
```
NOTICE metini: MODEL_ID not AWRF in data  -> default vertical interpolation
WARNING metini: FLUXES not found in data  -> Setting KBLS=2 to use the wind/temp profiles
```

## Files untouched / housekeeping
- The original 500 m results (`hysplit_lahore\lahore_backtraj_endpoints.csv`, SHA-256 `52bd34cf…82a8`,
  and its `failed_days.csv`) were not modified. All 72 `.gbl` files and the 2,161 `_500m` tdump files
  are unchanged.
- New tdump files: `D:\hysplit_met\_runs\tdump\tdump_YYYYMMDD_06_100m` and `_250m` (2,161 each).
- The run overwrites the scratch files in `D:\hysplit_met\_runs` (`CONTROL`, `MESSAGE`, `WARNING`,
  `TRAJ.CFG`, `ASCDATA.CFG`). The pre-run copies were saved to
  `D:\hysplit_multi\_runs_scratch_before_multiheight\` (not included in the zip).
- No clustering or analysis was done.
