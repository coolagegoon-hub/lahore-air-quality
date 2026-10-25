@echo off
REM One year of Lahore back-trajectories with GDAS 1 deg meteorology (comparison with the 2.5 deg run).
REM See LAPTOP_RUN_gdas1.md. Usage (from data\raw\hysplit):   scripts\run_gdas1.bat

if not exist C:\HYSPLIT\exec\hyts_std.exe (echo HYSPLIT not found at C:\HYSPLIT\exec\hyts_std.exe & exit /b 1)
if not exist D:\hysplit_gdas1_out mkdir D:\hysplit_gdas1_out

echo === Part 1: download and verify 61 GDAS 1 deg files (about 30 GB) ===
python -I scripts\download_met.py --dataset gdas1 --dest D:\hysplit_gdas1 --first-day 2024-02-27 --last-day 2025-02-28
if errorlevel 1 (echo Some files are not verified yet. Run this batch file again to resume. & exit /b 1)

echo === Part 2: trajectories, 2024-03-01 to 2025-02-28, 06 UTC, 100/250/500 m ===
python -I scripts\run_trajectories.py --dataset gdas1 --hyts C:\HYSPLIT\exec\hyts_std.exe ^
    --met D:\hysplit_gdas1 --runs D:\hysplit_gdas1\_runs ^
    --out D:\hysplit_gdas1_out\lahore_backtraj_gdas1_endpoints.csv ^
    --start 2024-03-01 --end 2025-02-28 --hour 6 --height 100 250 500
