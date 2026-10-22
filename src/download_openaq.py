"""Download OpenAQ AWS-archive daily files for one location, with a verified manifest.

Source: public S3 bucket ``openaq-data-archive`` (anonymous HTTPS access), documented at
https://docs.openaq.org/aws/about. Key pattern:
``records/csv.gz/locationid={id}/year={YYYY}/month={MM}/location-{id}-{YYYYMMDD}.csv.gz``

Each file is verified against the S3 listing: byte size must match, and for single-part
uploads (ETag without "-") the MD5 must equal the ETag. Already-downloaded files that pass
verification are not re-downloaded.

Usage:
    python -m src.download_openaq --location-id 8664
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import certifi

BUCKET_URL = "https://openaq-data-archive.s3.amazonaws.com"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Explicit CA bundle: python.org macOS builds do not use the system trust store.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


@dataclass(frozen=True)
class S3Object:
    key: str
    size: int
    etag: str
    last_modified: str


def _get(url: str, retries: int = 4, timeout: int = 60) -> bytes:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout, context=SSL_CONTEXT) as resp:
                return resp.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def list_objects(prefix: str) -> list[S3Object]:
    """List all objects under a prefix using paginated ListObjectsV2."""
    objects: list[S3Object] = []
    token = None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        root = ET.fromstring(_get(f"{BUCKET_URL}/?{urllib.parse.urlencode(params)}"))
        for c in root.findall("s3:Contents", S3_NS):
            objects.append(
                S3Object(
                    key=c.findtext("s3:Key", namespaces=S3_NS),
                    size=int(c.findtext("s3:Size", namespaces=S3_NS)),
                    etag=c.findtext("s3:ETag", namespaces=S3_NS).strip('"'),
                    last_modified=c.findtext("s3:LastModified", namespaces=S3_NS),
                )
            )
        if root.findtext("s3:IsTruncated", namespaces=S3_NS) != "true":
            break
        token = root.findtext("s3:NextContinuationToken", namespaces=S3_NS)
    return objects


def _verify(data: bytes, obj: S3Object) -> tuple[bool, str]:
    if len(data) != obj.size:
        return False, f"size {len(data)} != {obj.size}"
    if "-" not in obj.etag and hashlib.md5(data).hexdigest() != obj.etag:
        return False, "md5 != etag"
    return True, "ok"


def fetch_object(obj: S3Object, out_dir: Path, prefix: str) -> dict:
    dest = out_dir / obj.key[len(prefix):]
    status = "downloaded"
    if dest.exists() and _verify(dest.read_bytes(), obj)[0]:
        data, status = dest.read_bytes(), "existing"
    else:
        data = _get(f"{BUCKET_URL}/{urllib.parse.quote(obj.key)}")
        ok, msg = _verify(data, obj)
        if not ok:
            return {"key": obj.key, "status": f"FAILED: {msg}"}
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return {
        "key": obj.key,
        "local_path": str(dest.relative_to(PROJECT_ROOT)),
        "size_bytes": obj.size,
        "s3_etag": obj.etag,
        "s3_last_modified": obj.last_modified,
        "sha256": hashlib.sha256(data).hexdigest(),
        "status": status,
    }


def download_location(location_id: int, out_dir: Path, manifest_path: Path, workers: int = 16) -> list[dict]:
    prefix = f"records/csv.gz/locationid={location_id}/"
    objects = list_objects(prefix)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda o: fetch_object(o, out_dir, prefix), objects))
    rows.sort(key=lambda r: r["key"])

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["key", "local_path", "size_bytes", "s3_etag", "s3_last_modified", "sha256", "status"]
    with manifest_path.open("w", newline="") as f:
        f.write(f"# OpenAQ location {location_id}; listed and downloaded {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        f.write(f"# source: {BUCKET_URL}/{prefix}\n")
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--location-id", type=int, required=True)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    out_dir = PROJECT_ROOT / "data" / "raw" / "openaq" / f"location_{args.location_id}"
    manifest = PROJECT_ROOT / "results" / "tables" / f"openaq_{args.location_id}_download_manifest.csv"
    rows = download_location(args.location_id, out_dir, manifest, args.workers)

    failed = [r for r in rows if r["status"].startswith("FAILED")]
    print(f"objects listed: {len(rows)}")
    for s in sorted({r['status'] for r in rows}):
        print(f"  {s}: {sum(r['status'] == s for r in rows)}")
    print(f"manifest: {manifest.relative_to(PROJECT_ROOT)}")
    if failed:
        raise SystemExit(f"{len(failed)} files failed verification")


if __name__ == "__main__":
    main()
