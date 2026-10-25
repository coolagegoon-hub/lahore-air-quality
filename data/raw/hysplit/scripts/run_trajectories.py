"""Run one HYSPLIT back-trajectory per day and collect all endpoints into one CSV.

For each arrival day it writes a CONTROL file, runs hyts_std.exe, and keeps the
tdump file. Days whose tdump already exists are not re-run, so the script can be
restarted. Endpoints from every tdump are then written to the output CSV, and any
day that did not produce a full 72 h trajectory is listed in failed_days.csv.

No clustering is done here (clustering happens later, inside walk-forward
validation, to avoid leakage).

Usage:
    python -I run_trajectories.py --hyts C:\\hysplit\\exec\\hyts_std.exe ^
        --met D:\\hysplit_met --runs D:\\hysplit_met\\_runs ^
        --out <hysplit_lahore>\\lahore_backtraj_endpoints.csv
"""
import argparse
import csv
import datetime as dt
import os
import shutil
import subprocess

LAT, LON = 31.560078, 74.33589  # U.S. Consulate Lahore PM2.5 monitor


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def met_files_for(arrival, hours_back, dataset="reanalysis"):
    """Met files covering [arrival - hours_back, arrival]: reanalysis monthly files, or
    GDAS 1 deg weekly files (w1 = days 1-7, ..., w5 = days 29-31)."""
    start = arrival - dt.timedelta(hours=hours_back)
    if dataset == "gdas1":
        names, day = [], start.date()
        while day <= arrival.date():
            name = f"gdas1.{MONTHS[day.month - 1]}{day.year % 100:02d}.w{(day.day - 1) // 7 + 1}"
            if name not in names:
                names.append(name)
            day += dt.timedelta(days=1)
        return names
    names, y, m = [], start.year, start.month
    while (y, m) <= (arrival.year, arrival.month):
        names.append(f"RP{y:04d}{m:02d}.gbl")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return names


def write_control(path, arrival, height, hours_back, met_dir, met_names, out_dir, out_name):
    lines = [
        arrival.strftime("%y %m %d %H"),
        "1",
        f"{LAT:.6f} {LON:.6f} {height:.1f}",
        f"{-hours_back}",
        "0",          # vertical motion: use met model vertical velocity
        "10000.0",    # top of model domain, m AGL
        f"{len(met_names)}",
    ]
    for name in met_names:
        lines += [met_dir.rstrip("\\") + "\\", name]
    lines += [out_dir.rstrip("\\") + "\\", out_name]
    with open(path, "w", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def parse_tdump(path):
    """Yield endpoint dicts from a HYSPLIT trajectory endpoints (tdump) file.

    Format per the HYSPLIT User's Guide, section S263.
    """
    with open(path) as f:
        tokens = [line.split() for line in f if line.strip()]
    i = 0
    ngrid = int(tokens[i][0]); i += 1 + ngrid
    ntraj = int(tokens[i][0]); i += 1 + ntraj
    nvar = int(tokens[i][0]); labels = tokens[i][1:1 + nvar]; i += 1
    for t in tokens[i:]:
        yy, mm, dd, hh, mi = map(int, t[2:7])
        year = yy + (2000 if yy < 50 else 1900)
        diag = dict(zip(labels, map(float, t[12:12 + nvar])))
        yield {
            "traj": int(t[0]),
            "point_time": dt.datetime(year, mm, dd, hh, mi),
            "age_h": float(t[8]),
            "lat": float(t[9]),
            "lon": float(t[10]),
            "height_m_agl": float(t[11]),
            "pressure_hpa": diag.get("PRESSURE", ""),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hyts", required=True, help="path to hyts_std.exe")
    ap.add_argument("--met", required=True, help="directory with the met files (RPyyyymm.gbl or gdas1.*)")
    ap.add_argument("--runs", required=True, help="working dir for CONTROL/tdump (no spaces)")
    ap.add_argument("--out", required=True, help="output endpoints CSV")
    ap.add_argument("--start", default="2019-04-01")
    ap.add_argument("--end", default="2025-02-28")
    ap.add_argument("--hour", type=int, nargs="+", default=[6], help="arrival hour(s) UTC")
    ap.add_argument("--height", type=float, nargs="+", default=[500.0], help="arrival height(s) m AGL")
    ap.add_argument("--hours-back", type=int, default=72)
    ap.add_argument("--dataset", choices=["reanalysis", "gdas1"], default="reanalysis",
                    help="meteorology file naming: reanalysis RPyyyymm.gbl (default) or gdas1 weekly")
    args = ap.parse_args()

    if " " in args.runs or " " in args.met:
        raise SystemExit("--runs and --met must not contain spaces (HYSPLIT CONTROL paths)")
    tdump_dir = os.path.join(args.runs, "tdump")
    os.makedirs(tdump_dir, exist_ok=True)

    # hyts_std looks for ASCDATA.CFG in the working dir. The installed copy points to the
    # terrain/land-use files with a relative '../bdyfiles/', which is wrong from --runs,
    # so write a copy with the absolute bdyfiles path.
    bdy_dir = os.path.join(os.path.dirname(os.path.dirname(args.hyts)), "bdyfiles")
    src = os.path.join(bdy_dir, "ASCDATA.CFG")
    if os.path.exists(src):
        with open(src) as f:
            lines = f.read().splitlines()
        lines = [f"'{bdy_dir.rstrip(os.sep)}{os.sep}' directory location of data files"
                 if "directory location" in line else line for line in lines]
        with open(os.path.join(args.runs, "ASCDATA.CFG"), "w", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")

    day = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    runs = []
    while day <= end:
        for hour in args.hour:
            for height in args.height:
                runs.append((dt.datetime(day.year, day.month, day.day, hour), height))
        day += dt.timedelta(days=1)

    failed = []
    for arrival, height in runs:
        out_name = f"tdump_{arrival:%Y%m%d_%H}_{int(height)}m"
        out_path = os.path.join(tdump_dir, out_name)
        if os.path.exists(out_path):
            continue
        met_names = met_files_for(arrival, args.hours_back, args.dataset)
        missing = [n for n in met_names if not os.path.exists(os.path.join(args.met, n))]
        if missing:
            failed.append((arrival, height, "missing met: " + " ".join(missing)))
            continue
        write_control(os.path.join(args.runs, "CONTROL"), arrival, height, args.hours_back,
                      args.met, met_names, tdump_dir, out_name)
        p = subprocess.run([args.hyts], cwd=args.runs, capture_output=True, text=True)
        if p.returncode != 0 or not os.path.exists(out_path):
            msg = (p.stdout + p.stderr).strip().splitlines()[-1:] or ["no output"]
            failed.append((arrival, height, f"hyts_std rc={p.returncode}: {msg[0]}"))
            # Keep the MESSAGE file for diagnosis.
            msgf = os.path.join(args.runs, "MESSAGE")
            if os.path.exists(msgf):
                shutil.copy(msgf, os.path.join(args.runs, f"MESSAGE_{out_name}"))

    n_rows = 0
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arrival_time_utc", "arrival_height_m_agl", "hour_back", "point_time_utc",
                    "lat", "lon", "height_m_agl", "pressure_hpa"])
        for arrival, height in runs:
            out_path = os.path.join(tdump_dir, f"tdump_{arrival:%Y%m%d_%H}_{int(height)}m")
            if not os.path.exists(out_path):
                continue
            pts = list(parse_tdump(out_path))
            ages = [p["age_h"] for p in pts]
            if not pts or min(ages) > -args.hours_back:
                failed.append((arrival, height,
                               f"short trajectory: {len(pts)} endpoints, min age {min(ages, default=0)} h"))
            for p in pts:
                w.writerow([f"{arrival:%Y-%m-%dT%H:%M:%SZ}", height, int(round(-p["age_h"])),
                            f"{p['point_time']:%Y-%m-%dT%H:%M:%SZ}", p["lat"], p["lon"],
                            p["height_m_agl"], p["pressure_hpa"]])
                n_rows += 1

    fail_path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "failed_days.csv")
    with open(fail_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arrival_time_utc", "arrival_height_m_agl", "reason"])
        for arrival, height, reason in failed:
            w.writerow([f"{arrival:%Y-%m-%dT%H:%M:%SZ}", height, reason])

    print(f"runs requested: {len(runs)}, endpoint rows: {n_rows}, problems: {len(failed)}")
    print(f"endpoints -> {args.out}\nproblems  -> {fail_path}")


if __name__ == "__main__":
    main()
