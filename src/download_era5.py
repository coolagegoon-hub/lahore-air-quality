"""Download the ERA5 point time series for the Lahore PM2.5 monitor from the Copernicus CDS.

Dataset: reanalysis-era5-single-levels-timeseries (ERA5 hourly time-series data on single
levels), as set by the user on 2026-10-20, point 31.56 N 74.34 E (U.S. Consulate Lahore
monitor location, rounded), dates 2019-04-01 → 2025-02-28, CSV. The four ocean-only variables
in the user's selection (waves, sea surface temperature) were dropped because they are empty
over land; 19 variables remain. Requested one calendar year at a time (CDS refused the single
full-period request: "cost limits exceeded"). Times in the files are UTC.

Credentials: cdsapi reads CDSAPI_URL / CDSAPI_KEY from the environment or ~/.cdsapirc. A local
.env file (git-ignored) is loaded with python-dotenv if present. The key is never printed.

Output per year: data/raw/era5/era5_ts_<start>_<end>.<ext> plus a .provenance.json with the
request, retrieval time, size and SHA-256. Re-running skips years already downloaded.

Usage:
    python -m src.download_era5
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import cdsapi
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "era5"

DATASET = "reanalysis-era5-single-levels-timeseries"
REQUEST = {
    "variable": [
        "100m_u_component_of_wind",
        "100m_v_component_of_wind",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "10m_wind_gust_since_previous_post_processing",
        "2m_dewpoint_temperature",
        "2m_temperature",
        "boundary_layer_height",
        "cloud_base_height",
        "mean_sea_level_pressure",
        "skin_temperature",
        "surface_latent_heat_flux",
        "surface_pressure",
        "surface_sensible_heat_flux",
        "surface_solar_radiation_downwards",
        "surface_thermal_radiation_downwards",
        "total_cloud_cover",
        "total_precipitation",
        "total_sky_direct_solar_radiation_at_surface",
    ],
    "location": {"longitude": 74.34, "latitude": 31.56},
    "data_format": "csv",
}
# One request per chunk: a single 2019-04-01/2025-02-28 request was refused by CDS on
# 2026-10-20 with "cost limits exceeded".
FIRST_DATE, LAST_DATE = "2019-04-01", "2025-02-28"


def date_chunks(first: str = FIRST_DATE, last: str = LAST_DATE) -> list[str]:
    """Calendar-year chunks "YYYY-MM-DD/YYYY-MM-DD" covering first..last inclusive."""
    a, b = datetime.fromisoformat(first), datetime.fromisoformat(last)
    out = []
    for y in range(a.year, b.year + 1):
        lo = max(a, datetime(y, 1, 1)).strftime("%Y-%m-%d")
        hi = min(b, datetime(y, 12, 31)).strftime("%Y-%m-%d")
        out.append(f"{lo}/{hi}")
    return out


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    has_env = bool(os.environ.get("CDSAPI_KEY"))
    has_rc = (Path.home() / ".cdsapirc").exists()
    if not (has_env or has_rc):
        raise SystemExit("No CDS credentials found: add CDSAPI_URL and CDSAPI_KEY to .env, or create ~/.cdsapirc.")
    print(f"credentials: {'.env/environment' if has_env else '~/.cdsapirc'} (key not shown)", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client()
    for chunk in date_chunks():
        tag = chunk.replace("/", "_")
        prov_path = OUT_DIR / f"era5_ts_{tag}.provenance.json"
        if prov_path.exists():
            print(f"{chunk}: already downloaded, skipping", flush=True)
            continue
        request = {**REQUEST, "date": [chunk]}
        started = datetime.now(timezone.utc)
        result = client.retrieve(DATASET, request)
        suffix = Path(urlparse(result.location).path).suffix or ".csv"
        target = OUT_DIR / f"era5_ts_{tag}{suffix}"
        result.download(str(target))
        data = target.read_bytes()
        prov = {
            "dataset": DATASET,
            "request": request,
            "server_filename": Path(urlparse(result.location).path).name,
            "requested_utc": started.isoformat(timespec="seconds"),
            "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "file": str(target.relative_to(PROJECT_ROOT)),
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "time_zone_of_data": "UTC",
            "licence": "Copernicus licence (accepted by the user on the CDS dataset page)",
        }
        prov_path.write_text(json.dumps(prov, indent=2))
        print(f"{chunk}: {prov['file']} {len(data):,} bytes", flush=True)

if __name__ == "__main__":
    main()
