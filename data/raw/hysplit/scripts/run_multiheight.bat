@echo off
REM Extra HYSPLIT back-trajectories for Lahore: 100 m and 250 m AGL, arrival 06 UTC (as before).
REM Same HYSPLIT, meteorology and settings as the 500 m run. See LAPTOP_RUN_multiheight.md.
REM Usage (from data\raw\hysplit):   scripts\run_multiheight.bat

if not exist C:\HYSPLIT\exec\hyts_std.exe (echo HYSPLIT not found at C:\HYSPLIT\exec\hyts_std.exe & exit /b 1)
if not exist D:\hysplit_met\RP202502.gbl (echo Weather files not found in D:\hysplit_met & exit /b 1)
if not exist D:\hysplit_multi mkdir D:\hysplit_multi

echo Heights: 100 250 m   Arrival hour (UTC): 6
python -I scripts\run_trajectories.py --hyts C:\HYSPLIT\exec\hyts_std.exe ^
    --met D:\hysplit_met --runs D:\hysplit_met\_runs ^
    --out D:\hysplit_multi\lahore_backtraj_multiheight_endpoints.csv ^
    --start 2019-04-01 --end 2025-02-28 --hour 6 --height 100 250
