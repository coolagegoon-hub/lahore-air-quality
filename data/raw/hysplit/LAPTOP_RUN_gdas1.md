# Laptop run: one year of trajectories with sharper weather data (GDAS 1°)

Run this on the Windows processing laptop (the one with `C:\HYSPLIT`). It recomputes **one year** of trajectories (arrivals 1 March 2024 to 28 February 2025) with NOAA's **GDAS 1°** meteorology instead of the 2.5° NCEP/NCAR Reanalysis. It is a comparison only: the existing trajectories and weather files are not touched. Plan: `results/tables/stage9c_gdas_predeclaration.md`.

## What it does

| | Existing run | This run |
|---|---|---|
| Meteorology | NCEP/NCAR Reanalysis 2.5°, monthly files in `D:\hysplit_met\` | **GDAS 1°**, weekly files, downloaded to `D:\hysplit_gdas1\` |
| Download | done | **61 files, about 30 GB** (needs about 31 GB free on D:) |
| Days | 2019-04-01 to 2025-02-28 | **2024-03-01 to 2025-02-28** (365 days) |
| Heights | 500 m (plus 100 m and 250 m) | 500 m, 250 m and 100 m |
| Arrival, duration, vertical motion, model top | 06 UTC, 72 h, met vertical velocity, 10,000 m | unchanged |
| Trajectories | — | 1,095 (365 days × 3 heights) |

## Steps

1. **Update the scripts:** in the project folder, run `git pull`. Two scripts get a new `--dataset gdas1` option. Their old behaviour is unchanged.
2. **Check the space:** open *This PC* and check that **D:** has at least **31 GB free**. Keep the charger in and sleep set to *Never*.
3. **Download and run.** Open *Command Prompt* in `data\raw\hysplit` and type:

   ```bat
   scripts\run_gdas1.bat
   ```

   - **Part 1 (download):** 61 files from `https://www.ready.noaa.gov/data/archives/gdas1/`, one at a time as NOAA asks.
     - Each file is checked against NOAA's published MD5 and recorded in `D:\hysplit_gdas1\manifest.csv`.
     - This is the slow part: probably a few hours, depending on the internet speed.
     - If it stops, run the same command again. Finished files are skipped and partial files resume.
   - **Part 2 (trajectories):** starts only when every file is verified. It should take a few minutes.
   - Output goes to `D:\hysplit_gdas1_out\`.
4. **Check the result:**
   - The download should end with `done: 61 files requested, 0 not verified`.
   - The trajectory run should end with `runs requested: 1095, endpoint rows: 79935, problems: 0`.
   - `D:\hysplit_gdas1_out\failed_days.csv` should contain only its header.
5. **Bring it back:**
   - Zip `D:\hysplit_gdas1_out\` and also include `D:\hysplit_gdas1\manifest.csv`.
   - Send the zip to the Mac (into the project's `data/raw/hysplit/` folder) together with the final screen lines.
   - The CSV is about 6 MB.
6. **Free the space (only after the Mac has confirmed the zip is fine):** delete the folder `D:\hysplit_gdas1\` (the 30 GB of GDAS files). The manifest records every file's name, size and checksum, so the same files can be downloaded again if ever needed.

## What the batch file runs

```bat
python -I scripts\download_met.py --dataset gdas1 --dest D:\hysplit_gdas1 --first-day 2024-02-27 --last-day 2025-02-28
python -I scripts\run_trajectories.py --dataset gdas1 --hyts C:\HYSPLIT\exec\hyts_std.exe --met D:\hysplit_gdas1 --runs D:\hysplit_gdas1\_runs --out D:\hysplit_gdas1_out\lahore_backtraj_gdas1_endpoints.csv --start 2024-03-01 --end 2025-02-28 --hour 6 --height 100 250 500
```

The download starts on 27 February 2024 because a trajectory arriving on 1 March reaches back 72 hours.

## Do not

- Do not change any setting other than what the batch file runs.
- Do not use the `D:\hysplit_met` folders for this run, or write output into them.
- Do no analysis on the laptop. The comparison is done on the Mac under the approved plan.
