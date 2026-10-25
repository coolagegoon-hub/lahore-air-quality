"""Data figures for the paper (static PNG + PDF, light theme for print).

Fig 1  Weekly mean PM2.5, eligible weeks, with Oct–Jan smog seasons shaded.
Fig 2  Seasonal cycle, small multiples sharing the month axis (one y-scale per panel):
       (a) weekly PM2.5 by month, (b) VIIRS fire detections by month and sector,
       (c) median hourly ventilation coefficient, (d) mean monthly rainfall.
Fig 3  Map of VIIRS vegetation-fire detections (density) with the feature rings and sectors.
Fig 4  Daily PM2.5 data availability (valid hours per day), one row per year.

Colors follow the dataviz reference palette: categorical slots 1–2 (blue #2a78d6, orange
#eb6834), sequential blue ramp, neutral surface/ink tokens. Inputs are the processed files of
src.stage2_weekly, src.firms_features, src.era5_features and src.mass_balance_features.
Data note printed on figures: PM2.5 = AirNow, U.S. Department of State (preliminary data).

Usage:
    python -m src.figures_data
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap, LogNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from src import era5_features as ef  # noqa: E402
from src import firms_features as ff  # noqa: E402
from src import mass_balance_features as mb  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROC = PROJECT_ROOT / "data" / "processed"
FIG_DIR = PROJECT_ROOT / "results" / "figures"

# palette tokens (dataviz reference instance, light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e1"
SHADE = "#f0efec"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SOURCE_NOTE = "PM2.5: U.S. Consulate Lahore monitor via EPA AirNow (U.S. Department of State); preliminary data."


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2, "ytick.color": INK_2,
        "text.color": INK, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.axisbelow": True, "lines.linewidth": 2, "legend.frameon": False,
        "font.family": "sans-serif",
    })


# no creation date in PDFs, so a rerun writes byte-identical files
NO_DATE = {"pdf": {"CreationDate": None}}


def save(fig, name: str) -> list[Path]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("png", "pdf"):
        p = FIG_DIR / f"{name}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight", metadata=NO_DATE.get(ext))
        paths.append(p)
    plt.close(fig)
    return paths


def smog_spans(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    spans = []
    for y in range(start.year - 1, end.year + 1):
        a, b = pd.Timestamp(f"{y}-10-01"), pd.Timestamp(f"{y + 1}-02-01")
        if b > start and a < end:
            spans.append((max(a, start), min(b, end)))
    return spans


def fig1_weekly_series(weekly: pd.DataFrame):
    w = weekly[~weekly["partial_week"]].copy()
    w["value"] = w["weekly_mean_observed_days"].where(w["eligible"])
    mid = w["week_start"] + pd.Timedelta(days=3)
    fig, ax = plt.subplots(figsize=(10, 3.8))
    for a, b in smog_spans(mid.min(), mid.max()):
        ax.axvspan(a, b, color=SHADE, lw=0, zorder=0)
    ax.plot(mid, w["value"], color=BLUE, lw=2, solid_capstyle="round")
    ax.scatter(mid, w["value"], s=10, color=BLUE, zorder=3)
    i = w["value"].idxmax()
    ax.annotate(f"{w.loc[i, 'value']:.0f} µg/m³\nweek of {w.loc[i, 'week_start']:%d %b %Y}",
                xy=(mid[i], w.loc[i, "value"]), xytext=(15, -10), textcoords="offset points",
                fontsize=9, color=INK_2, va="top")
    ax.set_ylabel("Weekly mean PM2.5 (µg/m³)")
    ax.set_ylim(0, None)
    ax.set_title("Weekly mean PM2.5, Lahore, May 2019 – Feb 2025", loc="left")
    n_el, n_full = int(w["eligible"].sum()), len(w)
    ax.text(0.0, -0.2, f"Eligible weeks (≥ 6 of 7 valid days): {n_el} of {n_full}; gaps = ineligible weeks. "
            f"Grey bands: Oct–Jan smog season.\n{SOURCE_NOTE}", transform=ax.transAxes, fontsize=8, color=INK_2, va="top")
    return save(fig, "fig1_weekly_pm25")


def fig2_seasonal(weekly: pd.DataFrame, fire_daily: pd.DataFrame, hourly_box: pd.DataFrame, era5_daily: pd.DataFrame):
    fig, axes = plt.subplots(4, 1, figsize=(8, 10), sharex=True, gridspec_kw={"hspace": 0.35})
    x = np.arange(1, 13)

    # (a) weekly PM2.5 by month (Thursday month)
    w = weekly[weekly["eligible"] & ~weekly["partial_week"]].copy()
    w["month"] = (w["week_start"] + pd.Timedelta(days=3)).dt.month
    data = [w.loc[w["month"] == m, "weekly_mean_observed_days"].to_numpy() for m in x]
    bp = axes[0].boxplot(data, positions=x, widths=0.55, patch_artist=True, showfliers=True,
                         medianprops={"color": INK, "lw": 1.5}, flierprops={"marker": "o", "ms": 3,
                         "mfc": BLUE, "mec": BLUE, "alpha": 0.6}, whiskerprops={"color": INK_2},
                         capprops={"color": INK_2}, boxprops={"color": BLUE})
    for b in bp["boxes"]:
        b.set_facecolor(SEQ[1])
    axes[0].set_ylabel("µg/m³")
    axes[0].set_title("(a) Weekly mean PM2.5 by month", loc="left")

    # (b) fires per month by sector (mean per calendar year present)
    f = fire_daily.copy()
    f["month"], f["year"] = f.index.month, f.index.year
    per_month = f.groupby(["year", "month"])[["east_se_count", "west_s_count"]].sum().groupby("month").mean()
    width = 0.38
    axes[1].bar(x - width / 2 - 0.01, per_month["east_se_count"].reindex(x), width, color=BLUE,
                label="East / south-east sector, bearing 45–180° (mostly Indian Punjab and Haryana)")
    axes[1].bar(x + width / 2 + 0.01, per_month["west_s_count"].reindex(x), width, color=ORANGE,
                label="West / south sector, bearing 180–315° (mostly Pakistan)")
    axes[1].legend(loc="upper left", fontsize=8.5)
    axes[1].set_ylabel("detections / month")
    axes[1].set_title("(b) VIIRS vegetation-fire detections within 500 km, mean per month", loc="left")

    # (c) median hourly ventilation coefficient
    vc = hourly_box.groupby(hourly_box["day"].dt.month)["vc"].median().reindex(x)
    axes[2].bar(x, vc, 0.6, color=BLUE)
    axes[2].set_ylabel("m² s⁻¹")
    axes[2].set_title("(c) Ventilation coefficient (boundary-layer height × 10 m wind), median hour", loc="left")

    # (d) mean monthly rainfall
    d = era5_daily[era5_daily["complete_day"]].copy()
    d["month"], d["year"] = d.index.month, d.index.year
    rain = d.groupby(["year", "month"])["tp_sum_mm"].sum().groupby("month").mean().reindex(x)
    axes[3].bar(x, rain, 0.6, color=BLUE)
    axes[3].set_ylabel("mm / month")
    axes[3].set_title("(d) Rainfall (ERA5), mean per month", loc="left")
    axes[3].set_xticks(x, MONTHS)
    for ax in axes:
        ax.set_ylim(0, None)
        ax.grid(axis="x", visible=False)
    axes[3].text(0.0, -0.32, "Months with partial data in the first/last year are averaged over the years available. "
                 "ERA5 grid point 31.50 N, 74.25 E.\n" + SOURCE_NOTE, transform=axes[3].transAxes,
                 fontsize=8, color=INK_2, va="top")
    return save(fig, "fig2_seasonal_cycle")


def _circle(lat0, lon0, r_km, n=361):
    """Points at great-circle distance r_km from (lat0, lon0)."""
    R = ff.EARTH_R_KM
    br = np.radians(np.linspace(0, 360, n))
    p0, l0, d = np.radians(lat0), np.radians(lon0), r_km / R
    p = np.arcsin(np.sin(p0) * np.cos(d) + np.cos(p0) * np.sin(d) * np.cos(br))
    l = l0 + np.arctan2(np.sin(br) * np.sin(d) * np.cos(p0), np.cos(d) - np.sin(p0) * np.sin(p))
    return np.degrees(p), np.degrees(l)


def _ray(lat0, lon0, bearing_deg, r_km):
    R = ff.EARTH_R_KM
    p0, l0, b, d = np.radians(lat0), np.radians(lon0), np.radians(bearing_deg), np.linspace(0, r_km, 50) / R
    p = np.arcsin(np.sin(p0) * np.cos(d) + np.cos(p0) * np.sin(d) * np.cos(b))
    l = l0 + np.arctan2(np.sin(b) * np.sin(d) * np.cos(p0), np.cos(d) - np.sin(p0) * np.sin(p))
    return np.degrees(p), np.degrees(l)


BORDERS = PROJECT_ROOT / "data" / "raw" / "natural_earth" / "ne_10m_admin_0_boundary_lines_land.geojson"
COASTLINE = PROJECT_ROOT / "data" / "raw" / "natural_earth" / "ne_50m_coastline.geojson"


def draw_borders(ax, path: Path = BORDERS, bbox: tuple = (66, 81, 24, 38)) -> None:
    """Natural Earth 1:10m land boundary lines (public domain): international boundaries solid,
    disputed / line-of-control / indefinite boundaries dashed. Lines entirely outside bbox
    (lon_min, lon_max, lat_min, lat_max) are skipped."""
    import json

    g = json.loads(path.read_text())
    for f in g["features"]:
        cla = (f["properties"].get("FEATURECLA") or "").lower()
        geom = f["geometry"]
        lines = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
        disputed = any(k in cla for k in ("disputed", "line of control", "indefinite", "indeterminant", "unrecognized"))
        for line in lines:
            xy = np.asarray(line)
            if xy[:, 0].max() < bbox[0] or xy[:, 0].min() > bbox[1] or xy[:, 1].max() < bbox[2] or xy[:, 1].min() > bbox[3]:
                continue
            ax.plot(xy[:, 0], xy[:, 1], color=INK, lw=1.3 if not disputed else 1.0,
                    ls="-" if not disputed else (0, (4, 2)), zorder=4, solid_capstyle="round")
    draw_coastline(ax, bbox=bbox)


def draw_coastline(ax, path: Path = COASTLINE, bbox: tuple = (66, 81, 24, 38)) -> None:
    """Natural Earth 1:50m coastline (public domain), so land borders end at a drawn coast."""
    import json

    if not path.exists():
        return
    for f in json.loads(path.read_text())["features"]:
        geom = f["geometry"]
        lines = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
        for line in lines:
            xy = np.asarray(line)
            if xy[:, 0].max() < bbox[0] or xy[:, 0].min() > bbox[1] or xy[:, 1].max() < bbox[2] or xy[:, 1].min() > bbox[3]:
                continue
            ax.plot(xy[:, 0], xy[:, 1], color=INK_2, lw=0.8, zorder=4, solid_capstyle="round")


def fig3_fire_map(kept: pd.DataFrame):
    lat0, lon0 = ff.LAHORE
    fig, ax = plt.subplots(figsize=(7.5, 7))
    cmap = ListedColormap(SEQ)
    hb = ax.hexbin(kept["longitude"], kept["latitude"], gridsize=110, extent=(69, 78, 27, 35),
                   bins=None, norm=LogNorm(vmin=1), cmap=cmap, mincnt=1, linewidths=0)
    cb = fig.colorbar(hb, ax=ax, shrink=0.7, pad=0.02)
    cb.set_label("Detections per cell, Apr 2019 – Feb 2025 (log scale)")
    halo = [pe.withStroke(linewidth=3, foreground=SURFACE)]
    draw_borders(ax)
    for name, x, y in (("PAKISTAN", 70.4, 32.6), ("INDIA", 76.9, 30.4)):
        ax.text(x, y, name, fontsize=10, color=INK_2, fontweight="bold", ha="center",
                path_effects=halo, zorder=6)
    for r in (100, 300, 500):
        la, lo = _circle(lat0, lon0, r)
        ax.plot(lo, la, color=INK_2, lw=1, ls="--")
        # label just inside the ring, on the south side, left of the 180° sector line
        ax.text(lon0 - 0.08, lat0 - r / 111.2 + 0.12, f"{r} km", fontsize=8.5, color=INK, ha="right",
                va="bottom", path_effects=halo, zorder=6)
    for b in (45, 180, 315):
        la, lo = _ray(lat0, lon0, b, 500)
        ax.plot(lo, la, color=INK, lw=1.2)
    ax.text(76.0, 29.4, "East / south-east\nsector", fontsize=9, ha="center", color=INK, fontweight="bold",
            path_effects=halo, zorder=6)
    ax.text(71.6, 30.2, "West / south\nsector", fontsize=9, ha="center", color=INK, fontweight="bold",
            path_effects=halo, zorder=6)
    ax.plot(lon0, lat0, marker="*", ms=14, color=ORANGE, mec=INK, mew=0.8, zorder=7)
    ax.annotate("Lahore PM2.5 monitor", (lon0, lat0), xytext=(10, 6), textcoords="offset points",
                fontsize=9, fontweight="bold", path_effects=halo, zorder=7)
    ax.set_xlim(69, 78)
    ax.set_ylim(27, 35)
    ax.set_aspect(1 / np.cos(np.radians(31)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("VIIRS (Suomi NPP) vegetation-fire detections and feature regions", loc="left")
    ax.text(0.0, -0.1, "Nominal/high-confidence vegetation fires (type 0). Rings: 0–100, 100–300, 300–500 km; "
            "sector lines at bearings 45°, 180°, 315°.\nThe download box (69–78 E, 27–35 N) truncates the 300–500 km ring "
            "to the east and north. Sectors are\ngeometric (by bearing), not national: the east/south-east sector "
            "also contains Pakistani districts south-east of Lahore.\nBorders: Natural Earth 1:10m (public domain); dashed = disputed or line of control. "
            "Boundary depiction does not imply any position on disputed territory.", transform=ax.transAxes, fontsize=8,
            color=INK_2, va="top")
    return save(fig, "fig3_fire_map")


def fig4_availability(daily: pd.DataFrame):
    d = daily.copy()
    d["year"], d["doy"] = d.index.year, d.index.day_of_year
    years = sorted(d["year"].unique())
    grid = np.full((len(years), 366), np.nan)
    for i, y in enumerate(years):
        s = d[d["year"] == y]
        grid[i, s["doy"].to_numpy() - 1] = s["hours_valid"].to_numpy()
    cats = np.where(np.isnan(grid), np.nan, np.select([grid == 0, grid < 18, grid < 24], [0, 1, 2], 3))
    # ordinal steps 250/400/600 of the blue ramp: validated (validateOrdinal, light, surface #fcfcfb)
    ordinal = ["#86b6ef", "#3987e5", "#184f95"]
    cmap = ListedColormap([SHADE] + ordinal)
    cmap.set_bad(SURFACE)
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.imshow(np.ma.masked_invalid(cats), aspect="auto", cmap=cmap, norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], 4),
              interpolation="nearest", extent=(0.5, 366.5, len(years) - 0.5, -0.5))
    ax.set_yticks(range(len(years)), years)
    starts = pd.date_range("2021-01-01", periods=12, freq="MS").day_of_year
    ax.set_xticks(starts, MONTHS)
    ax.grid(False)
    for i in range(len(years) + 1):
        ax.axhline(i - 0.5, color=SURFACE, lw=2)
    ax.legend(handles=[Patch(color=SHADE, label="0 h (no data)"), Patch(color=ordinal[0], label="1–17 h (incomplete)"),
                       Patch(color=ordinal[1], label="18–23 h (valid day)"), Patch(color=ordinal[2], label="24 h")],
              loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, fontsize=8.5)
    ax.set_title("Daily PM2.5 data availability: valid hours per day", loc="left")
    n_ok = int((d["hours_valid"] >= 18).sum())
    ax.text(0.0, -0.32, f"{n_ok} of {len(d)} days have ≥ 18 valid hours (after QC). White = outside the record. "
            + SOURCE_NOTE, transform=ax.transAxes, fontsize=8, color=INK_2, va="top")
    return save(fig, "fig4_data_availability")


def main() -> None:
    style()
    weekly = pd.read_csv(PROC / "pm25_weekly_target.csv", parse_dates=["week_start", "week_end"])
    pm_daily = pd.read_csv(PROC / "pm25_daily_final.csv", parse_dates=["date"], index_col="date")
    fire_daily = pd.read_csv(PROC / "firms_viirs_snpp_daily_pkt.csv", parse_dates=["date"], index_col="date")
    era5_daily = pd.read_csv(PROC / "era5_daily_pkt.csv", parse_dates=["date"], index_col="date")
    hourly_box = mb.hourly_box(ef.to_hourly_pkt(ef.load_raw()))
    kept = ff.prepare(ff.load_source(ff.PRIMARY))
    out = []
    out += fig1_weekly_series(weekly)
    out += fig2_seasonal(weekly, fire_daily, hourly_box, era5_daily)
    out += fig3_fire_map(kept)
    out += fig4_availability(pm_daily)
    for p in out:
        print(p.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
