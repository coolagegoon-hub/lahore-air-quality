"""Download NASA FIRMS active-fire detections (standard-processing archives) around Lahore.

API: https://firms.modaps.eosdis.nasa.gov/api/area/ (checked 2026-10-20)
    /api/area/csv/[MAP_KEY]/[SOURCE]/[west,south,east,north]/[DAY_RANGE]/[DATE]
    DAY_RANGE 1–5 days; DATE is the first day; limit 5000 transactions / 10 min.
Sources: MODIS_SP, VIIRS_SNPP_SP, VIIRS_NOAA20_SP (science-quality archives; availability
checked 2026-10-21 via /api/data_availability: all cover 2019-04-01 → 2025-02-28).
Area: BBOX = 69–78 E, 27–35 N (Pakistani and Indian Punjab, Haryana and surroundings).
Deliberately generous so the region used for features can be chosen later without
re-downloading. Detection dates/times in FIRMS are UTC.

The key comes from FIRMS_MAP_KEY in the git-ignored .env (python-dotenv) and is never printed
or written to the manifest.

Output: data/raw/firms/<SOURCE>/<start-date>.csv per 5-day chunk, plus
data/raw/firms/manifest_<SOURCE>.csv (chunk, rows, bytes, sha256, fetched time).
Re-running skips chunks already saved.

Usage:
    python -m src.download_firms
"""

from __future__ import annotations

import csv
import hashlib
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from src.airnow_archive import SSL_CONTEXT

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "firms"
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCES = ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "MODIS_SP")
BBOX = (69.0, 27.0, 78.0, 35.0)  # west, south, east, north
FIRST_DATE, LAST_DATE = "2019-04-01", "2025-02-28"
DAY_RANGE = 5
PAUSE_SECONDS = 1.5  # <= ~40 requests/min, well under 5000 transactions / 10 min


def chunks(first: str = FIRST_DATE, last: str = LAST_DATE, step: int = DAY_RANGE) -> list[tuple[str, int]]:
    """(start date, number of days) pairs covering first..last inclusive."""
    a, b = pd.Timestamp(first), pd.Timestamp(last)
    out = []
    d = a
    while d <= b:
        n = min(step, (b - d).days + 1)
        out.append((d.strftime("%Y-%m-%d"), n))
        d += pd.Timedelta(days=n)
    return out


def fetch(key: str, source: str, start: str, ndays: int, retries: int = 4) -> bytes:
    bbox = ",".join(f"{v:g}" for v in BBOX)
    url = f"{API}/{key}/{source}/{bbox}/{ndays}/{start}"
    last = ""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180, context=SSL_CONTEXT) as resp:
                data = resp.read()
            head = data[:200].decode("utf-8", "replace")
            if head.startswith("latitude"):
                return data
            last = head.strip().replace(key, "[REDACTED]")[:120]  # API returned a message, not CSV
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
        except Exception as e:
            last = type(e).__name__
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{source} {start}: {last}")


def run_source(key: str, source: str) -> pd.DataFrame:
    d = OUT_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    mpath = OUT_DIR / f"manifest_{source}.csv"
    rows = pd.read_csv(mpath).to_dict("records") if mpath.exists() else []
    done = {r["chunk_start"] for r in rows}
    todo = [(s, n) for s, n in chunks() if s not in done]
    print(f"[{source}] {len(todo)} chunks to fetch ({len(done)} already done)", flush=True)
    for i, (start, n) in enumerate(todo, 1):
        data = fetch(key, source, start, n)
        (d / f"{start}.csv").write_bytes(data)
        nrows = max(sum(1 for _ in csv.reader(data.decode("utf-8").splitlines())) - 1, 0)
        rows.append({"chunk_start": start, "days": n, "rows": nrows, "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest(),
                     "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        if i % 50 == 0 or i == len(todo):
            pd.DataFrame(rows).to_csv(mpath, index=False)
            print(f"[{source}] {i}/{len(todo)}", flush=True)
        time.sleep(PAUSE_SECONDS)
    man = pd.DataFrame(rows).sort_values("chunk_start")
    man.to_csv(mpath, index=False)
    return man


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.environ.get("FIRMS_MAP_KEY")
    if not key:
        raise SystemExit("FIRMS_MAP_KEY not found in .env")
    for source in SOURCES:
        man = run_source(key, source)
        print(f"[{source}] chunks={len(man)} detections={int(man['rows'].sum())} bytes={int(man['bytes'].sum())}", flush=True)


if __name__ == "__main__":
    main()
