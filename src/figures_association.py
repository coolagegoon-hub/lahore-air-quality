"""Figures for the Stage 7 pathway association analysis (static PNG + PDF), drawn only from the
saved outputs in results/tables/stage7/ (run src.association_analysis first). Journal style:
white background, no in-figure titles or notes (the paper's captions carry them).

Fig 10  Mean paths of the descriptive trajectory clusters, with their frequency.
Fig 11  Daily PM2.5 by cluster within each season (box plots, n per box).
Fig 12  Daily PM2.5 against 72-h transport distance, by season (binned medians and IQR).
Fig 13  Trajectory-weighted fire exposure against the PM2.5 anomaly, October-November days.
Fig 14  Trajectory endpoint frequency and concentration-weighted trajectory (CWT) maps,
        post-monsoon and winter.

Usage:
    python -m src.figures_association
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402

from src import figures_data as fd  # noqa: E402
from src import firms_features as ff  # noqa: E402
from src import trajectory_features as tf  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
S7 = PROJECT_ROOT / "results" / "tables" / "stage7"
SEASONS = ["winter", "pre-monsoon", "monsoon", "post-monsoon"]
SEASON_LABEL = {"winter": "Winter (Dec–Feb)", "pre-monsoon": "Pre-monsoon (Mar–May)",
                "monsoon": "Monsoon (Jun–Sep)", "post-monsoon": "Post-monsoon (Oct–Nov)"}
CLUSTER_COLORS = {1: fd.BLUE, 2: fd.ORANGE, 3: "#6b6b6b"}
JOURNAL = {"figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
           "font.size": 8.5, "axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
           "axes.titlesize": 8.5, "axes.titleweight": "normal", "axes.grid": False}
PM_LABEL = "Daily PM$_{2.5}$ (µg m$^{-3}$)"


def km_to_lonlat(x, y):
    lat0, lon0 = ff.LAHORE
    lat = lat0 + np.degrees(np.asarray(y) / ff.EARTH_R_KM)
    lon = lon0 + np.degrees(np.asarray(x) / (ff.EARTH_R_KM * np.cos(np.radians(lat0))))
    return lon, lat


def clean(ax, grid_y=True):
    ax.spines[["top", "right"]].set_visible(False)
    if grid_y:
        ax.grid(axis="y", color="#e3e3e3", lw=0.6)
        ax.set_axisbelow(True)


def fig10_paths(summ: pd.DataFrame, paths: pd.DataFrame):
    with plt.rc_context(JOURNAL):
        fig, ax = plt.subplots(figsize=(5.6, 4.4))
        fd.draw_borders(ax, bbox=(30, 85, 20, 45))
        lat0, lon0 = ff.LAHORE
        for _, r in summ.iterrows():
            c = int(r["cluster"])
            row = paths.loc[c]
            xs = [0.0] + [row[f"x{h}"] for h in tf.SHAPE_HOURS]
            ys = [0.0] + [row[f"y{h}"] for h in tf.SHAPE_HOURS]
            lon, lat = km_to_lonlat(xs, ys)
            col = CLUSTER_COLORS.get(c, "black")
            ax.plot(lon, lat, color=col, lw=2.2, zorder=3,
                    label=f"C{c}: {r['speed']}, from {r['from_dir']} ({r['share_pct']:.0f}% of days)")
            ax.scatter(lon[1:], lat[1:], s=10, color=col, zorder=4)
            ax.annotate(f"C{c}", (lon[-1], lat[-1]), xytext=(4, 4), textcoords="offset points", fontsize=8, color=col)
        ax.scatter([lon0], [lat0], marker="*", s=120, color="black", zorder=5, label="Lahore monitor")
        ax.set_xlim(33, 82)
        ax.set_ylim(22, 42)
        ax.set_aspect(1 / np.cos(np.radians(32)))
        ax.set_xlabel("Longitude (°E)")
        ax.set_ylabel("Latitude (°N)")
        ax.legend(loc="lower left", fontsize=7.5, frameon=True, framealpha=0.9, edgecolor="#cccccc")
        clean(ax, grid_y=False)
        fig.tight_layout()
        return fd.save(fig, "fig10_cluster_paths")


def fig11_boxes(days: pd.DataFrame, k: int):
    with plt.rc_context(JOURNAL):
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.9), sharey=True)
        for ax, s in zip(axes, SEASONS):
            ds = days[days["season"] == s]
            data, labels, cols = [], [], []
            for c in range(1, k + 1):
                v = ds.loc[ds["cluster"] == c, "pm25_daily_mean"]
                data.append(v.to_numpy() if len(v) else np.array([np.nan]))
                labels.append(f"C{c}\nn={len(v)}")
                cols.append(CLUSTER_COLORS.get(c, "black") if len(v) >= 30 else "#d0d0d0")
            bp = ax.boxplot(data, widths=0.6, patch_artist=True, showfliers=False,
                            medianprops={"color": "black", "lw": 1.2})
            for patch, col in zip(bp["boxes"], cols):
                patch.set_facecolor(col)
                patch.set_alpha(0.75)
            ax.set_xticks(range(1, k + 1), labels, fontsize=7.5)
            ax.set_title(SEASON_LABEL[s], loc="left")
            clean(ax)
        axes[0].set_ylabel(PM_LABEL)
        fig.tight_layout(w_pad=0.6)
        return fd.save(fig, "fig11_pm_by_cluster")


def fig12_distance(days: pd.DataFrame):
    with plt.rc_context(JOURNAL):
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.6), sharey=True)
        for ax, s in zip(axes, SEASONS):
            ds = days[days["season"] == s]
            q = pd.qcut(ds["traj_mean_dist72_km"], 8, duplicates="drop")
            g = ds.groupby(q, observed=True).agg(x=("traj_mean_dist72_km", "median"), med=("pm25_daily_mean", "median"),
                                                 lo=("pm25_daily_mean", lambda v: v.quantile(.25)),
                                                 hi=("pm25_daily_mean", lambda v: v.quantile(.75)))
            ax.scatter(ds["traj_mean_dist72_km"], ds["pm25_daily_mean"], s=3, color="#bdbdbd", lw=0, zorder=1)
            ax.fill_between(g["x"], g["lo"], g["hi"], color=fd.BLUE, alpha=0.18, lw=0, zorder=2)
            ax.plot(g["x"], g["med"], color=fd.BLUE, lw=1.6, marker="o", ms=3, zorder=3)
            ax.set_xscale("log")
            ax.set_xlim(20, 8000)
            ax.set_title(SEASON_LABEL[s], loc="left")
            clean(ax)
        axes[0].set_ylabel(PM_LABEL)
        axes[0].set_ylim(0, 600)
        fig.supxlabel("72-h transport distance from Lahore (km, log scale)", fontsize=8.5, y=0.02)
        fig.tight_layout(w_pad=0.6)
        return fd.save(fig, "fig12_pm_vs_distance")


def fig13_fire(days: pd.DataFrame):
    on = days[(days["season"] == "post-monsoon") & days["fe_50km"].notna()].copy()
    on["x"] = np.log1p(on["fe_50km"])
    q = pd.qcut(on["x"], 6, duplicates="drop")
    g = on.groupby(q, observed=True).agg(x=("x", "median"), med=("anom", "median"),
                                         lo=("anom", lambda v: v.quantile(.25)), hi=("anom", lambda v: v.quantile(.75)))
    with plt.rc_context(JOURNAL):
        fig, ax = plt.subplots(figsize=(3.5, 3.0))
        ax.axhline(0, color="#999999", lw=0.7)
        ax.scatter(on["x"], on["anom"], s=6, color="#bdbdbd", lw=0, zorder=1)
        ax.fill_between(g["x"], g["lo"], g["hi"], color=fd.ORANGE, alpha=0.2, lw=0, zorder=2)
        ax.plot(g["x"], g["med"], color=fd.ORANGE, lw=1.6, marker="o", ms=3, zorder=3)
        ax.set_xlabel("log(1 + fire exposure, MW)")
        ax.set_ylabel("PM$_{2.5}$ anomaly (log units)")
        clean(ax)
        fig.tight_layout()
        return fd.save(fig, "fig13_fire_exposure")


def fig14_cwt():
    with plt.rc_context(JOURNAL):
        fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4), sharex=True, sharey=True)
        lat0, lon0 = ff.LAHORE
        for row, s in enumerate(["post-monsoon", "winter"]):
            g = pd.read_csv(S7 / f"cwt_{s}.csv")
            for col, (field, cmap, norm, label) in enumerate([
                    ("n", "Greys", LogNorm(vmin=1, vmax=max(10, g["n"].max())), "Endpoints per 1° cell"),
                    ("wcwt", "YlOrRd", None, "Weighted CWT (µg m$^{-3}$)")]):
                short = "endpoint frequency" if field == "n" else "weighted CWT"
                ax = axes[row, col]
                piv = g.pivot(index="iy", columns="ix", values=field)
                xs = np.append(piv.columns.to_numpy(), piv.columns.max() + 1)
                ys = np.append(piv.index.to_numpy(), piv.index.max() + 1)
                mesh = ax.pcolormesh(xs, ys, piv.to_numpy(), cmap=cmap, norm=norm, shading="flat", zorder=1)
                fd.draw_borders(ax, bbox=(50, 85, 20, 42))
                ax.scatter([lon0], [lat0], marker="*", s=70, color=fd.BLUE, zorder=5)
                ax.set_xlim(55, 82)
                ax.set_ylim(22, 40)
                ax.set_aspect(1 / np.cos(np.radians(31)))
                ax.set_title(f"({'abcd'[row * 2 + col]}) {SEASON_LABEL[s]}: {short}", loc="left")
                cb = fig.colorbar(mesh, ax=ax, shrink=0.8, pad=0.02)
                cb.set_label(label, fontsize=7.5)
                cb.ax.tick_params(labelsize=7)
                clean(ax, grid_y=False)
        for ax in axes[1]:
            ax.set_xlabel("Longitude (°E)")
        for ax in axes[:, 0]:
            ax.set_ylabel("Latitude (°N)")
        fig.tight_layout()
        return fd.save(fig, "fig14_cwt_maps")


def main() -> None:
    summ = pd.read_csv(S7 / "cluster_summary.csv")
    paths = pd.read_csv(S7 / "cluster_mean_paths_km.csv", index_col="cluster")
    days = pd.read_csv(S7 / "analysis_days.csv", parse_dates=["date"])
    k = int(summ["cluster"].max())
    out = fig10_paths(summ, paths) + fig11_boxes(days, k) + fig12_distance(days) + fig13_fire(days) + fig14_cwt()
    for p in out:
        print(p.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
