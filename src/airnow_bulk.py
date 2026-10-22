"""Size-verified bulk extraction of one site's lines from AirNow hourly archive files.

For each GMT day the S3 listing (key + size) is retrieved first. Every HourlyData file not
already cached is downloaded in full, its byte count is checked against both the listed size
and the HTTP Content-Length, and only lines containing the AQS ID are written to the same cache
used by src.airnow_archive (so ``airnow_archive.hourly`` reads them afterwards). Cache files are
written atomically (temp file + rename), so an interrupted run leaves no partial cache entries;
re-running resumes where it stopped.

A manifest per calendar year is written to data/raw/airnow_files/manifests/:
key, listed_size, bytes_read, content_length, n_lines, status, fetched_utc
status is one of:
    downloaded_verified  bytes == listed size == Content-Length
    cached_unverified    cache existed before this tool (Stage 1C sample weeks); size not recorded
    cached_verified      verified by an earlier run of this tool
    FAILED_size          size mismatch after retries; no cache written
    FAILED_error         network/HTTP error after retries; no cache written

Usage:
    python -m src.airnow_bulk --aqsid 586PK3010003 --start 2019-05-21 --end 2025-02-18 --workers 8
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src import airnow_archive as aa

LIST_URL = "https://s3-us-west-1.amazonaws.com/files.airnowtech.org/"
MANIFEST_COLUMNS = ["key", "listed_size", "bytes_read", "content_length", "n_lines", "status", "fetched_utc"]


def manifest_dir() -> Path:
    return aa.CACHE_DIR / "manifests"


def list_day(day: pd.Timestamp) -> list[tuple[str, int]]:
    url = f"{LIST_URL}?list-type=2&prefix=airnow/{day:%Y}/{day:%Y%m%d}/HourlyData_"
    with urllib.request.urlopen(url, timeout=120, context=aa.SSL_CONTEXT) as resp:
        xml = resp.read().decode()
    keys = re.findall(r"<Key>([^<]*)</Key>", xml)
    sizes = [int(s) for s in re.findall(r"<Size>(\d+)</Size>", xml)]
    if len(keys) != len(sizes) or "<IsTruncated>true</IsTruncated>" in xml:
        raise RuntimeError(f"unexpected listing for {day:%Y-%m-%d}")
    return list(zip(keys, sizes))


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def fetch_verified(key: str, listed_size: int, aqsid: str, retries: int = 4) -> dict:
    relpath = key.removeprefix("airnow/")
    cache = aa.CACHE_DIR / aqsid / relpath
    row = {"key": key, "listed_size": listed_size, "bytes_read": None, "content_length": None,
           "n_lines": None, "status": None, "fetched_utc": None}
    if cache.exists():
        row["n_lines"] = cache.read_text().count("\n")
        row["status"] = "cached_unverified"
        return row
    last_err = ""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(f"{aa.BASE_URL}/{relpath}", timeout=180, context=aa.SSL_CONTEXT) as resp:
                clen = resp.headers.get("Content-Length")
                data = resp.read()
            row.update(bytes_read=len(data), content_length=int(clen) if clen else None)
            if len(data) != listed_size or (clen is not None and int(clen) != len(data)):
                last_err = "size"
                time.sleep(2 ** attempt)
                continue
            text = data.decode("latin-1")
            lines = "".join(line + "\n" for line in text.splitlines() if aqsid in line)
            _write_atomic(cache, lines)
            row.update(n_lines=lines.count("\n"), status="downloaded_verified",
                       fetched_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            return row
        except Exception as e:  # network errors: retry, then record
            last_err = f"error: {type(e).__name__}"
            time.sleep(2 ** attempt)
    row["status"] = "FAILED_size" if last_err == "size" else "FAILED_error"
    return row


def run_year(year: int, start: pd.Timestamp, end: pd.Timestamp, aqsid: str, workers: int) -> pd.DataFrame:
    days = pd.date_range(max(start, pd.Timestamp(f"{year}-01-01")), min(end, pd.Timestamp(f"{year}-12-31")), freq="D")
    with ThreadPoolExecutor(max_workers=8) as pool:
        listing = [kv for kvs in pool.map(list_day, days) for kv in kvs]

    mpath = manifest_dir() / f"hourly_{aqsid}_{year}.csv"
    previous = pd.read_csv(mpath).set_index("key") if mpath.exists() else pd.DataFrame(columns=MANIFEST_COLUMNS).set_index("key")
    verified_before = set(previous.index[previous["status"].isin(["downloaded_verified", "cached_verified"])])

    t0, done, rows = time.time(), 0, []
    total_bytes = sum(s for k, s in listing if k not in verified_before)

    def task(kv):
        key, size = kv
        if key in verified_before:
            r = previous.loc[key].to_dict() | {"key": key, "status": "cached_verified"}
            return r
        return fetch_verified(key, size, aqsid)

    def save(rows_so_far: list[dict]) -> pd.DataFrame:
        # keep earlier verified rows not yet reprocessed, so a checkpoint never loses them
        new = pd.DataFrame(rows_so_far, columns=MANIFEST_COLUMNS)
        old = previous.reset_index()
        old = old[~old["key"].isin(new["key"])] if len(old) else old
        man = pd.concat([old, new], ignore_index=True).sort_values("key")[MANIFEST_COLUMNS]
        mpath.parent.mkdir(parents=True, exist_ok=True)
        man.to_csv(mpath, index=False)
        return man

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(task, listing):
            rows.append(r)
            done += 1
            if done % 500 == 0 or done == len(listing):
                el = time.time() - t0
                print(f"[{year}] {done}/{len(listing)} files, {el / 60:.1f} min elapsed", flush=True)
                save(rows)

    man = save(rows)
    man = man[man["key"].isin([k for k, _ in listing])]
    print(f"[{year}] listed={len(listing)} bytes_to_fetch={total_bytes / 1e9:.2f} GB "
          f"status={man['status'].value_counts().to_dict()} lines={int(man['n_lines'].fillna(0).sum())}", flush=True)
    return man


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aqsid", required=True)
    ap.add_argument("--start", required=True, help="first GMT date, YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="last GMT date, YYYY-MM-DD")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    failed = 0
    for year in range(start.year, end.year + 1):
        man = run_year(year, start, end, args.aqsid, args.workers)
        failed += int(man["status"].str.startswith("FAILED").sum())
    print(f"DONE failed_files={failed}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
