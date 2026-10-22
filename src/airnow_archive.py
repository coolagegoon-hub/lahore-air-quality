"""Extract one site's records from the public AirNow file archive (files.airnowtech.org).

Archive layout (verified 2026-10-18): ``airnow/YYYY/YYYYMMDD/`` holds
- ``HourlyData_YYYYMMDDhh.dat``: one hour, all sites, pipe-delimited. Per the AirNow
  "Hourly Data File" fact sheet (updated Aug 2025), date/time are GMT and mark the
  BEGINNING of the measurement period; only valid data are included.
- ``daily_data_v2.dat``: daily peak/average values, "midnight-to-midnight, begin-hour,
  and Local Standard Time" (AirNow "Daily Data File" fact sheet, Aug 2025).
- ``monitoring_site_locations.dat``: site metadata.

These are AirNow's near-real-time products ("not fully verified or validated; ... preliminary").
Each archive file is ~0.8-1.3 MB and covers all sites, so only lines containing the requested
AQS ID are kept. Extracted lines are cached under data/raw/airnow_files/ (git-ignored).

Usage:
    python -m src.airnow_archive hourly --aqsid 586PK3010003 --start 2021-09-14 --end 2021-09-16
    python -m src.airnow_archive daily  --aqsid 586PK3010003 --start 2019-05-23 --end 2025-03-05
    python -m src.airnow_archive sites  --aqsid 586PK3010003 --date 2021-09-15
"""

from __future__ import annotations

import argparse
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import certifi
import pandas as pd

BASE_URL = "https://s3-us-west-1.amazonaws.com/files.airnowtech.org/airnow"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "airnow_files"
MISSING_MARKER = "#MISSING_FILE\n"  # cached when the archive has no such file (HTTP 403/404)

HOURLY_COLUMNS = ["valid_date", "valid_time", "aqsid", "sitename", "gmt_offset", "parameter", "units", "value", "data_source"]
DAILY_COLUMNS = [
    "valid_date", "aqsid", "sitename", "parameter", "units", "value", "averaging_period",
    "data_source", "aqi", "aqi_category", "latitude", "longitude", "full_aqsid",
]


def _fetch_lines(url: str, needle: str, retries: int = 4) -> str | None:
    """Return matching lines (possibly empty string), or None if the file does not exist."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120, context=SSL_CONTEXT) as resp:
                text = resp.read().decode("latin-1")
            return "".join(line + "\n" for line in text.splitlines() if needle in line)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            if attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def extract(relpath: str, needle: str) -> str | None:
    """Cached extraction of lines containing ``needle`` from one archive file."""
    cache = CACHE_DIR / needle / relpath
    if cache.exists():
        text = cache.read_text()
        return None if text == MISSING_MARKER else text
    lines = _fetch_lines(f"{BASE_URL}/{relpath}", needle)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(MISSING_MARKER if lines is None else lines)
    return lines


def _run(relpaths: list[str], needle: str, workers: int) -> list[tuple[str, str | None]]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(zip(relpaths, pool.map(lambda p: extract(p, needle), relpaths)))


def hourly(aqsid: str, start: str, end: str, workers: int = 12) -> pd.DataFrame:
    """Hourly records for GMT dates start..end inclusive. Adds tz-aware begin/end timestamps."""
    hours = pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    relpaths = [f"{h:%Y}/{h:%Y%m%d}/HourlyData_{h:%Y%m%d%H}.dat" for h in hours]
    results = _run(relpaths, aqsid, workers)
    rows = [line.split("|") for _, text in results if text for line in text.splitlines()]
    df = pd.DataFrame(rows, columns=HOURLY_COLUMNS)
    df = df[df["aqsid"] == aqsid]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    begin = pd.to_datetime(df["valid_date"] + " " + df["valid_time"], format="%m/%d/%y %H:%M", utc=True)
    df["period_begin_utc"] = begin
    df["period_end_local"] = (begin + pd.Timedelta(hours=1)).dt.tz_convert("Asia/Karachi")
    df.attrs["files_requested"] = len(relpaths)
    df.attrs["files_missing"] = sum(text is None for _, text in results)
    return df.drop_duplicates(["period_begin_utc", "parameter"]).sort_values("period_begin_utc").reset_index(drop=True)


def daily(aqsid: str, start: str, end: str, workers: int = 12) -> pd.DataFrame:
    """Daily records from each day's daily_data_v2.dat (the last file produced that day)."""
    days = pd.date_range(start, end, freq="D")
    relpaths = [f"{d:%Y}/{d:%Y%m%d}/daily_data_v2.dat" for d in days]
    results = _run(relpaths, aqsid, workers)
    rows = []
    for rel, text in results:
        for line in (text or "").splitlines():
            rows.append(line.split("|") + [rel])
    df = pd.DataFrame(rows, columns=DAILY_COLUMNS + ["archive_file"])
    df = df[df["aqsid"] == aqsid].copy()
    df["date"] = pd.to_datetime(df["valid_date"], format="%m/%d/%y")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df.attrs["files_requested"] = len(relpaths)
    df.attrs["files_missing"] = sum(text is None for _, text in results)
    return df.reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["hourly", "daily", "sites"])
    ap.add_argument("--aqsid", required=True)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--date")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    if args.kind == "sites":
        d = pd.Timestamp(args.date)
        print(extract(f"{d:%Y}/{d:%Y%m%d}/monitoring_site_locations.dat", args.aqsid))
        return
    df = (hourly if args.kind == "hourly" else daily)(args.aqsid, args.start, args.end, args.workers)
    print(df.to_string(max_rows=60))
    print(f"rows={len(df)} files_requested={df.attrs['files_requested']} files_missing={df.attrs['files_missing']}")


if __name__ == "__main__":
    main()
