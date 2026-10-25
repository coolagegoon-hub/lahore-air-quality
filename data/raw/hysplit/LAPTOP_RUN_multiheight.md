# Laptop run: extra trajectories at 100 m and 250 m

Run this on the Windows processing laptop (the one with `C:\HYSPLIT` and the weather files in `D:\hysplit_met\`). It uses the **same** HYSPLIT version, the same NCEP/NCAR 2.5° files and the same settings as the existing 500 m trajectories. Only the arrival height changes, and **nothing new is downloaded**.

## What it produces

| Setting | Existing run | This run |
|---|---|---|
| Arrival heights | 500 m | **100 m and 250 m** |
| Arrival time (UTC) | 06 (11:00 PKT) | 06 (11:00 PKT), unchanged |
| Days | 2019-04-01 to 2025-02-28 | the same 2,161 days |
| Duration, vertical motion, model top | 72 h, met vertical velocity, 10,000 m | unchanged |
| Number of trajectories | 2,161 | 4,322 (2,161 days × 2 heights) |

No clustering or analysis happens on the laptop. Any analysis of these trajectories will be pre-declared on the Mac first (Stage 9b).

## Steps

1. **Get the files.**
   - On the laptop, update the project folder from GitHub (`git pull`), or copy this file and `scripts\run_multiheight.bat` across.
   - `scripts\run_trajectories.py` is the same script used before, unchanged.
2. **Run the 100 m and 250 m trajectories.** Open *Command Prompt* in the `data\raw\hysplit` folder and type:

   ```bat
   scripts\run_multiheight.bat
   ```

   - It writes to a **new folder**, `D:\hysplit_multi\`, so the original `failed_days.csv` and endpoint file are not touched.
   - It reuses the run folder `D:\hysplit_met\_runs\`. Any trajectory already computed there is skipped, and the original 06 UTC, 500 m files are left as they are.
   - You can stop it with Ctrl+C and start it again later; finished trajectories are not redone.
   - It should take about twice as long as the original 500 m run, because each trajectory is run one at a time. Keep the laptop plugged in and stop it from sleeping.
3. **Check the result.**
   - The last two lines on screen give the number of runs, the number of endpoint rows and the number of problems.
   - Expected: `runs requested: 4322`, `endpoint rows: 315506` (4,322 × 73), and `problems: 0`.
   - Open `D:\hysplit_multi\failed_days.csv`. It should contain only the header line.
4. **Bring it back to the Mac.**
   - Zip `D:\hysplit_multi\` (the CSV is about 20 MB).
   - Copy the zip to the Mac, into `data/raw/hysplit/` in the project folder, and tell Claude it is there.
   - Also note the date and the final screen lines.

## What the batch file runs

```bat
python -I scripts\run_trajectories.py --hyts C:\HYSPLIT\exec\hyts_std.exe ^
    --met D:\hysplit_met --runs D:\hysplit_met\_runs ^
    --out D:\hysplit_multi\lahore_backtraj_multiheight_endpoints.csv ^
    --start 2019-04-01 --end 2025-02-28 --hour 6 --height 100 250
```

## Output columns

As in `README.md`. `arrival_time_utc` together with `arrival_height_m_agl` identifies each trajectory.
