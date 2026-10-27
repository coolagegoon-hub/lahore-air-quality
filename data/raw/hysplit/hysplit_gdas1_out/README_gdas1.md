# Lahore back-trajectories with GDAS 1° meteorology (one-year comparison run)

Run on 2026-10-27 (run_gdas1.bat 15:57–16:04 PKT) on the Windows processing laptop, following
`data/raw/hysplit/LAPTOP_RUN_gdas1.md`. The scripts are the repository versions, SHA-256 checked:
`run_gdas1.bat` 82251f2d…bf85, `download_met.py` 99357b82…dd95, `run_trajectories.py` 086c7f55…6521.

## Software and settings
- **HYSPLIT version: `hysplit.v5.4.2`** (from `MESSAGE`), `C:\HYSPLIT\exec\hyts_std.exe`. This is the same install as the 2.5° runs.
- Meteorology: **NOAA ARL GDAS 1°**, 61 weekly files `gdas1.feb24.w4` … `gdas1.feb25.w4`,
  31,912,208,960 bytes. All 61 have `status = ok` in `manifest.csv`, with MD5 equal to NOAA's `listing.md5.txt`.
- Receptor 31.560078 N, 74.33589 E. Arrival **06 UTC**, heights **100, 250 and 500 m AGL**.
  Arrival days **2024-03-01 to 2025-02-28** (365 days). 72 h back, vertical motion 0 (met vertical
  velocity), model top 10,000 m. These are the batch-file settings, unchanged.

## Commands run (from `run_gdas1.bat`)
```bat
python -I scripts\download_met.py --dataset gdas1 --dest D:\hysplit_gdas1 --first-day 2024-02-27 --last-day 2025-02-28
python -I scripts\run_trajectories.py --dataset gdas1 --hyts C:\HYSPLIT\exec\hyts_std.exe --met D:\hysplit_gdas1 --runs D:\hysplit_gdas1\_runs --out D:\hysplit_gdas1_out\lahore_backtraj_gdas1_endpoints.csv --start 2024-03-01 --end 2025-02-28 --hour 6 --height 100 250 500
```

## Final screen lines
```
done: 61 files requested, 0 not verified
runs requested: 1095, endpoint rows: 79935, problems: 0
```
`failed_days.csv` contains only its header, so **0 failed days**.

## Output
- `lahore_backtraj_gdas1_endpoints.csv`: 6,207,254 bytes, SHA-256
  **`46b1cd0496f4eabeede3fac6ac1ce27640ecc86f69a9aa99ea63e05048ad8ef7`**.
  The columns are the same as the earlier runs.
- Checks: 1,095 trajectories, each exactly 73 rows (hour_back 0–72). Heights are only 100.0, 250.0
  and 500.0; arrival hour is always 06; 365 days. No empty pressure values. Ground-level (0.0 m)
  endpoints: 1,203 at 100 m, 636 at 250 m and 332 at 500 m. These are model output, not missing values.
- `manifest.csv` (SHA-256 `b937816f5465adb61a5f9a94828069947e9eb1cc2a4e6dc619171b6f5f22e4cf`) is included alongside.

## Warnings
Only the expected notice:
`NOTICE metini: MODEL_ID not AWRF in data → default vertical interpolation`.
Unlike the 2.5° reanalysis runs, there was **no** `FLUXES not found` / `KBLS=2` warning, because GDAS
includes surface flux fields.

## How the GDAS files got here
- **31 files** were downloaded on this laptop directly from `https://www.ready.noaa.gov/data/archives/gdas1/`.
- **30 files** were downloaded on the Mac with the repository's `download_met.py`, then transferred as
  10 split zips. Every zip passed its CRC test, and every extracted file matched NOAA's MD5 before use.
- `run_gdas1.bat` Part 1 then re-hashed all 61 files against NOAA's MD5 and wrote `manifest.csv`.
  No file needed re-downloading.
- Downloads sometimes used more than NOAA's suggested 2 parallel connections. This does not affect the data,
  which every MD5 check confirms.
- No other setting was changed and no analysis was done.
