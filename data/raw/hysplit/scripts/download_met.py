"""Resumable download of NOAA ARL meteorology: NCEP/NCAR Reanalysis (2.5 deg) monthly files,
or (--dataset gdas1) GDAS 1 deg weekly files.

Each file is fetched with curl (resume with -C -), checked against the size the
server reports and against NOAA's published MD5 (listing.md5.txt), and recorded
in manifest.csv with its size, MD5 and SHA-256. Re-running skips files that are
already verified, so the script can be stopped and restarted at any time.

Usage:
    python -I download_met.py --dest D:\\hysplit_met --first 2019-03 --last 2025-02
    python -I download_met.py --dest D:\\hysplit_met --files RP201903.gbl
    python -I download_met.py --dataset gdas1 --dest D:\\hysplit_gdas1 --first-day 2024-02-27 --last-day 2025-02-28
"""
import argparse
import csv
import datetime as dt
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.request

BASE_URLS = {"reanalysis": "https://www.ready.noaa.gov/data/archives/reanalysis/",
             "gdas1": "https://www.ready.noaa.gov/data/archives/gdas1/"}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MANIFEST_FIELDS = ["file", "url", "bytes", "md5_noaa", "md5_local", "sha256",
                   "verified_utc", "status"]


def month_files(first, last):
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"RP{y:04d}{m:02d}.gbl")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def gdas1_name(day):
    """GDAS 1 deg weekly file holding this UTC day: w1 = days 1-7, w2 = 8-14, ..., w5 = 29-31."""
    return f"gdas1.{MONTHS[day.month - 1]}{day.year % 100:02d}.w{(day.day - 1) // 7 + 1}"


def gdas1_files(first_day, last_day):
    day, end, out = dt.date.fromisoformat(first_day), dt.date.fromisoformat(last_day), []
    while day <= end:
        name = gdas1_name(day)
        if name not in out:
            out.append(name)
        day += dt.timedelta(days=1)
    return out


def with_retries(fn, what, tries=8):
    # The ARL server often times out; back off and try again before giving up.
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == tries:
                raise
            wait = min(600, 30 * attempt)
            print(f"[retry] {what}: {e} (attempt {attempt}/{tries}, waiting {wait}s)", flush=True)
            time.sleep(wait)


def fetch_noaa_md5(cache_path, base_url):
    def get():
        with urllib.request.urlopen(base_url + "listing.md5.txt", timeout=120) as r:
            return r.read().decode("ascii", "replace")
    try:
        text = with_retries(get, "listing.md5.txt")
        with open(cache_path, "w", encoding="ascii") as f:
            f.write(text)
    except Exception:
        if not os.path.exists(cache_path):
            raise
        print(f"[warn] using cached {cache_path}")
        with open(cache_path, encoding="ascii") as f:
            text = f.read()
    md5 = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            md5[parts[1]] = parts[0].lower()
    return md5


def remote_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.headers["Content-Length"])


def hashes(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def load_manifest(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["file"]: row for row in csv.DictReader(f)}


def save_manifest(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for name in sorted(rows):
            w.writerow(rows[name])
    os.replace(tmp, path)


def download(url, part_path):
    # One connection at a time, as the ARL readme asks.
    cmd = [shutil.which("curl") or "curl", "-f", "-L", "-sS", "-C", "-", "--retry", "10",
           "--retry-delay", "30", "--retry-all-errors", "--connect-timeout", "60",
           # Treat < 1 KB/s for 5 min as a stall so curl drops it and retries (resuming).
           "--speed-limit", "1024", "--speed-time", "300",
           "-o", part_path, url]
    return subprocess.run(cmd).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(BASE_URLS), default="reanalysis")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--first-day", help="gdas1: first UTC day needed (YYYY-MM-DD)")
    ap.add_argument("--last-day", help="gdas1: last UTC day needed (YYYY-MM-DD)")
    ap.add_argument("--first", default="2019-03")
    ap.add_argument("--last", default="2025-02")
    ap.add_argument("--files", nargs="*", help="explicit file names instead of a month range")
    ap.add_argument("--manifest", help="default: <dest>/manifest.csv")
    args = ap.parse_args()

    os.makedirs(args.dest, exist_ok=True)
    manifest_path = args.manifest or os.path.join(args.dest, "manifest.csv")
    rows = load_manifest(manifest_path)
    base_url = BASE_URLS[args.dataset]
    noaa_md5 = fetch_noaa_md5(os.path.join(args.dest, "listing.md5.txt"), base_url)
    if args.files:
        names = args.files
    elif args.dataset == "gdas1":
        if not (args.first_day and args.last_day):
            raise SystemExit("--dataset gdas1 needs --first-day and --last-day")
        names = gdas1_files(args.first_day, args.last_day)
    else:
        names = month_files(args.first, args.last)
    failures = 0

    for name in names:
        url = base_url + name
        final = os.path.join(args.dest, name)
        part = final + ".part"
        prev = rows.get(name)
        if (prev and prev["status"] == "ok" and os.path.exists(final)
                and os.path.getsize(final) == int(prev["bytes"])):
            print(f"[skip] {name} already verified")
            continue

        try:
            size = with_retries(lambda: remote_size(url), f"HEAD {name}")
        except Exception as e:
            print(f"[fail] {name}: HEAD failed: {e}")
            failures += 1
            continue

        if not os.path.exists(final):
            print(f"[get ] {name} ({size:,} bytes)", flush=True)
            rc = download(url, part)
            if rc != 0 or not os.path.exists(part) or os.path.getsize(part) != size:
                got = os.path.getsize(part) if os.path.exists(part) else 0
                print(f"[fail] {name}: curl rc={rc}, have {got:,} of {size:,} bytes (re-run to resume)")
                failures += 1
                continue
            os.replace(part, final)

        md5_local, sha = hashes(final)
        md5_ref = noaa_md5.get(name, "")
        actual = os.path.getsize(final)
        if actual != size:
            status = f"size_mismatch(remote={size})"
        elif not md5_ref:
            status = "ok_no_noaa_md5"
        elif md5_ref == md5_local:
            status = "ok"
        else:
            status = "md5_mismatch"
        rows[name] = {
            "file": name, "url": url, "bytes": actual, "md5_noaa": md5_ref,
            "md5_local": md5_local, "sha256": sha,
            "verified_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
        }
        save_manifest(manifest_path, rows)
        print(f"[{'ok  ' if status == 'ok' else 'WARN'}] {name} {status} sha256={sha}")
        if status not in ("ok", "ok_no_noaa_md5"):
            failures += 1
            # Keep the bad file aside so the next run downloads a fresh copy.
            os.replace(final, final + ".bad")

    print(f"done: {len(names)} files requested, {failures} not verified")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
