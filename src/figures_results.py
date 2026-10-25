"""Results figures for the paper (static PNG + PDF), drawn only from saved walk-forward outputs.

Fig 6  MAE by method, all weeks vs Oct–Jan (common set).
Fig 7  Change in MAE when each input layer is added, and layer 5 vs baselines, with 95%
       moving-block bootstrap CIs (4-week blocks) from Stages 3 and 4.
Fig 8  Observed weekly PM2.5 vs (a) RF layer 5 and (b) Ridge PM2.5-history forecasts over the common set,
       two stacked panels in journal style (no in-figure title or notes).
Fig 9  Predicted vs observed (RF layer 5), with the 1:1 line.

No model is refitted here. Colors: dataviz reference palette via src.figures_data.

Usage:
    python -m src.figures_results
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import figures_data as fd  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TAB = PROJECT_ROOT / "results" / "tables"
METHODS = [
    ("persistence", "Persistence (last week)"),
    ("climatology", "Seasonal climatology"),
    ("history_model", "Ridge PM$_{2.5}$-history"),
    ("rf_L1_history", "RF L1: PM$_{2.5}$ history"),
    ("rf_L2_plus_era5", "RF L2: + ERA5 weather"),
    ("rf_L3_plus_fire", "RF L3: + FIRMS fire"),
    ("rf_L4_plus_massbalance", "RF L4: + mass balance"),
    ("rf_L5_plus_traj", "RF L5: + HYSPLIT trajectories"),
]
NOTE = ("Walk-forward forecasts, zero embargo; common set of eligible weeks 17 May 2021 – 10 Feb 2025. "
        "PM$_{2.5}$: U.S. Consulate Lahore via EPA AirNow\n(U.S. Department of State); preliminary data.")


def load_common() -> pd.DataFrame:
    p = pd.read_csv(TAB / "stage4" / "predictions_all_models.csv", parse_dates=["target_week_start"])
    cols = [m for m, _ in METHODS]
    common = p["observed_eligible"].eq(True) & p[cols].notna().all(axis=1)
    return p.loc[common].sort_values("target_week_start").reset_index(drop=True)


def fig6_mae(c: pd.DataFrame):
    labels = [lab for _, lab in METHODS][::-1]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True, gridspec_kw={"wspace": 0.08})
    for ax, (title, mask) in zip(axes, [(f"All weeks (n = {len(c)})", np.ones(len(c), bool)),
                                        (f"Oct–Jan weeks (n = {int(c['smog_season_week'].sum())})",
                                         c["smog_season_week"].to_numpy())]):
        mae = [float(np.abs(c.loc[mask, m] - c.loc[mask, "observed"]).mean()) for m, _ in METHODS][::-1]
        y = np.arange(len(labels))
        colors = [fd.BLUE if "RF" in lab else fd.SEQ[2] for lab in labels]
        ax.barh(y, mae, 0.62, color=colors)
        for yi, v in zip(y, mae):
            ax.text(v + 0.5, yi, f"{v:.1f}", va="center", fontsize=8.5, color=fd.INK_2)
        ax.set_title(title, loc="left")
        ax.set_xlim(0, max(mae) * 1.15)
        ax.set_xlabel("Mean absolute error (µg m$^{-3}$)")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(np.arange(len(labels)), labels)
    fig.suptitle("Forecast error by method: lower is better", x=0.125, ha="left", fontweight="bold", fontsize=11)
    fig.text(0.125, -0.06, "Lighter bars: reference baselines; darker bars: Random Forest input layers.\n" + NOTE,
             fontsize=8, color=fd.INK_2, va="top")
    return fd.save(fig, "fig6_mae_by_method")


def fig7_increments():
    s3 = pd.read_csv(TAB / "stage3" / "mae_difference_bootstrap.csv")
    s4 = pd.read_csv(TAB / "stage4" / "mae_difference_bootstrap.csv")
    s4 = s4[s4["block_weeks"] == 4].drop(columns="block_weeks")
    b = pd.concat([s3, s4], ignore_index=True)
    rows = [
        ("rf_L2_plus_era5", "rf_L1_history", "+ ERA5 weather (L2 vs L1)"),
        ("rf_L3_plus_fire", "rf_L2_plus_era5", "+ FIRMS fire (L3 vs L2)"),
        ("rf_L4_plus_massbalance", "rf_L3_plus_fire", "+ mass balance (L4 vs L3)"),
        ("rf_L5_plus_traj", "rf_L4_plus_massbalance", "+ HYSPLIT trajectories (L5 vs L4)"),
        ("rf_L5_plus_traj", "history_model", "L5 vs Ridge PM$_{2.5}$-history"),
        ("rf_L5_plus_traj", "climatology", "L5 vs seasonal climatology"),
        ("rf_L5_plus_traj", "persistence", "L5 vs persistence"),
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    n = len(rows)
    ypos = np.arange(n)[::-1].astype(float)
    ypos[4:] -= 0.6  # visual gap between increments and baseline comparisons
    for subset, color, marker, off, lab in (("all", fd.BLUE, "o", 0.16, "All weeks (n = 133)"),
                                            ("smog", fd.ORANGE, "s", -0.16, "Oct–Jan weeks (n = 52)")):
        for i, (a, b_, _) in enumerate(rows):
            r = b[(b["model"] == a) & (b["compared_to"] == b_) & (b["subset"] == subset)].iloc[0]
            ax.errorbar(r["mae_diff"], ypos[i] + off, xerr=[[r["mae_diff"] - r["ci95_low"]], [r["ci95_high"] - r["mae_diff"]]],
                        fmt=marker, color=color, ms=7, mec=fd.SURFACE, mew=1.2, elinewidth=2, capsize=0,
                        label=lab if i == 0 else None, zorder=3)
    ax.axvline(0, color=fd.INK, lw=1)
    ax.axhline((ypos[3] + ypos[4]) / 2, color=fd.GRID, lw=1)
    ax.set_yticks(ypos, [r[2] for r in rows])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in mean absolute error (µg m$^{-3}$); left of 0 = first model better")
    ax.legend(loc="upper left", fontsize=8.5)
    ax.set_title("What each input adds, with 95% bootstrap intervals", loc="left")
    ax.text(0.0, -0.17, "Intervals crossing 0: no reliable difference. Moving-block bootstrap, 4-week blocks, 2,000 resamples, "
            "paired by week.\n" + NOTE, transform=ax.transAxes, fontsize=8, color=fd.INK_2, va="top")
    return fd.save(fig, "fig7_layer_increments")


def fig8_timeseries(c: pd.DataFrame):
    """Two stacked panels in journal style (white background, no in-figure title or notes; the
    paper's caption carries them). Unlike the scores, which use the common set ``c``, this figure
    shows every eligible observed week and every forecast each model made over the common-set span,
    so that fewer weeks are missing. Solid lines join consecutive weeks; faint dotted lines cross
    weeks with no value, which are never filled in. One shared legend sits above the panels."""
    p = pd.read_csv(TAB / "stage4" / "predictions_all_models.csv", parse_dates=["target_week_start"])
    weeks = pd.date_range(c["target_week_start"].min(), c["target_week_start"].max(), freq="7D")
    s = pd.DataFrame({"target_week_start": weeks}).merge(p, on="target_week_start", how="left")
    s.loc[~s["observed_eligible"].eq(True), "observed"] = np.nan
    mid = s["target_week_start"] + pd.Timedelta(days=3)

    def line_with_gaps(ax, y, color, lw, z):
        ok = y.notna()
        ax.plot(mid[ok], y[ok], color=color, lw=0.6, ls=(0, (1, 1.5)), alpha=0.8, zorder=z - 1)  # across gaps
        ax.plot(mid, y, color=color, lw=lw, zorder=z)                                            # consecutive weeks

    with plt.rc_context({"figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
                         "font.size": 8.5, "axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8}):
        fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.9), sharex=True, sharey=True)
        panels = [("rf_L5_plus_traj", fd.BLUE, "(a) Random Forest, model 5 (all inputs)"),
                  ("history_model", fd.ORANGE, "(b) Ridge regression on past PM$_{2.5}$")]
        for ax, (col, color, label) in zip(axes, panels):
            for a_, b_ in fd.smog_spans(mid.min(), mid.max()):
                ax.axvspan(a_, b_, color="#efefef", lw=0, zorder=0)
            line_with_gaps(ax, s["observed"], "#444444", 0.8, 3)
            ax.scatter(mid, s["observed"], s=6, color="black", zorder=4, linewidths=0)
            line_with_gaps(ax, s[col], color, 1.3, 6)
            ax.set_ylim(0, 460)
            ax.set_yticks([0, 100, 200, 300, 400])
            ax.grid(False)
            ax.grid(axis="y", color="#e3e3e3", lw=0.6)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_title(label, loc="left", fontsize=8.5, fontweight="normal", pad=3)
            ax.set_ylabel("PM$_{2.5}$ (µg m$^{-3}$)")
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        handles = [Line2D([], [], color="#444444", lw=0.8, marker="o", ms=2.5, mfc="black", mec="black", label="Observed"),
                   Line2D([], [], color=fd.BLUE, lw=1.3, label="Random Forest forecast"),
                   Line2D([], [], color=fd.ORANGE, lw=1.3, label="Ridge forecast"),
                   Line2D([], [], color="#777777", lw=0.8, ls=(0, (1, 1.5)), label="Gap (no value)"),
                   Patch(facecolor="#efefef", label="October–January")]
        fig.legend(handles=handles, loc="upper center", ncol=5, frameon=False, fontsize=7.5,
                   bbox_to_anchor=(0.5, 1.0), handlelength=1.8, columnspacing=1.4)
        fig.align_ylabels(axes)
        fig.tight_layout(rect=(0, 0, 1, 0.94), h_pad=0.8)
        return fd.save(fig, "fig8_forecast_timeseries")


def fig9_scatter(c: pd.DataFrame):
    obs, pred = c["observed"].to_numpy(float), c["rf_L5_plus_traj"].to_numpy(float)
    smog = c["smog_season_week"].to_numpy()
    lim = float(max(obs.max(), pred.max()) * 1.05)
    fig, ax = plt.subplots(figsize=(5.6, 5.6))
    ax.plot([0, lim], [0, lim], color=fd.INK_2, lw=1, ls="--", zorder=1)
    ax.scatter(obs[~smog], pred[~smog], s=26, color=fd.BLUE, edgecolor=fd.SURFACE, lw=0.8, label=f"Other months (n = {int((~smog).sum())})", zorder=3)
    ax.scatter(obs[smog], pred[smog], s=26, color=fd.ORANGE, marker="s", edgecolor=fd.SURFACE, lw=0.8, label=f"Oct–Jan (n = {int(smog.sum())})", zorder=3)
    mae = float(np.abs(pred - obs).mean())
    r2 = 1 - float(((pred - obs) ** 2).sum()) / float(((obs - obs.mean()) ** 2).sum())
    ax.text(0.04, 0.96, f"RF L5, all {len(obs)} weeks\nMAE {mae:.1f} µg m$^{{-3}}$, R² {r2:.2f}", transform=ax.transAxes, va="top", fontsize=9)
    ax.text(lim * 0.97, lim * 0.78, "1:1 line", color=fd.INK_2, fontsize=8.5, ha="right", va="top")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("Observed weekly mean PM$_{2.5}$ (µg m$^{-3}$)")
    ax.set_ylabel("Forecast (µg m$^{-3}$)")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title("Forecast vs observed (RF layer 5)", loc="left")
    ax.text(0.0, -0.15, "Points below the 1:1 line are under-forecasts.\nPM$_{2.5}$: EPA AirNow (U.S. Dept. of State); preliminary data.",
            transform=ax.transAxes, fontsize=8, color=fd.INK_2, va="top")
    return fd.save(fig, "fig9_forecast_vs_observed")


def main() -> None:
    fd.style()
    c = load_common()
    out = fig6_mae(c) + fig7_increments() + fig8_timeseries(c) + fig9_scatter(c)
    for p in out:
        print(p.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
