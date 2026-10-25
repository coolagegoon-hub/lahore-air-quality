"""Stage 9b: do the pathway, stagnation, fire and forecast results change at 100 m and 250 m?

Design pre-declared in results/tables/stage9b_multiheight_predeclaration.md (committed de3fc1d before
the 100 m and 250 m trajectories reached the Mac). The 500 m results (Stages 4, 7, 8) are unchanged and
remain primary; the lower heights are a declared sensitivity analysis.

Input: data/raw/hysplit/lahore_backtraj_multiheight_endpoints.csv (laptop run of 2026-10-25,
HYSPLIT v5.4.2, NCEP/NCAR 2.5°, 72 h, arrival 06 UTC at 100 m and 250 m AGL).

Usage:
    python -m src.stage9b_multiheight
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import association_analysis as aa
from src import era5_features as ef
from src import firms_features as ff
from src import mass_balance_features as mbf
from src import stage4_trajectory_model as s4
from src import stage8_robustness as s8
from src import trajectory_features as tf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MULTI = PROJECT_ROOT / "data" / "raw" / "hysplit" / "multiheight" / "lahore_backtraj_multiheight_endpoints.csv"
EXPECTED_SHA256 = "679683366ae21ef5e078f89aac2217d0b025c0e2d53c1bd50bc0173224571ebb"
S7 = PROJECT_ROOT / "results" / "tables" / "stage7"
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage9b"
HEIGHTS = (100.0, 250.0)
N_POINTS = 73
MAX_FAIL_SHARE = 0.01
ADJUST = ["log_vc", "ws10", "t2m", "rh", "rain_day"]


# ------------------------------------------------------------------ inputs

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_inputs(ends: pd.DataFrame, dates_500: pd.DatetimeIndex) -> dict:
    """Per height: trajectories, 73 points each, arrival at 06 UTC, same PKT days as the 500 m set.
    Raises if a height is missing more than MAX_FAIL_SHARE of the 500 m days."""
    out = {}
    for h in HEIGHTS:
        e = ends[ends["arrival_height_m_agl"] == h]
        n_pts = e.groupby("arrival_utc").size()
        full = n_pts[n_pts == N_POINTS].index
        hours = sorted(pd.DatetimeIndex(e["arrival_utc"].unique()).hour.unique().tolist())
        days = pd.DatetimeIndex(full).tz_convert(tf.TZ).tz_localize(None).normalize()
        missing = dates_500.difference(days)
        out[f"{int(h)}m"] = {"trajectories": int(n_pts.size), "full_73_points": int(len(full)),
                             "arrival_hours_utc": hours, "days_missing_vs_500m": int(len(missing)),
                             "extra_days": int(len(days.difference(dates_500)))}
        if len(missing) > MAX_FAIL_SHARE * len(dates_500) or hours != [6]:
            raise SystemExit(f"input check failed at {h} m: {out[f'{int(h)}m']}")
    return out


def nearest_centre(traj: pd.DataFrame, centres: pd.DataFrame) -> np.ndarray:
    """Assign each trajectory to the nearest Stage 7 cluster centre (Euclidean, 24-number shape vector)."""
    cols = tf.shape_columns()
    X, C = traj[cols].to_numpy(float), centres[cols].to_numpy(float)
    d2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
    return centres.index.to_numpy()[d2.argmin(axis=1)]


def decoupling_verdict(ratio: float, lo: float, hi: float) -> str:
    if ratio > 1 and lo > 1:
        return "supported"
    if ratio > 1:
        return "partly supported"
    return "not supported"


# ------------------------------------------------------------------ main

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(aa.SEED)
    summary = {"predeclaration": "results/tables/stage9b_multiheight_predeclaration.md"}

    # 0. input checks
    digest = sha256(MULTI)
    summary["sha256"] = digest
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"SHA-256 mismatch: {digest}")
    ends = pd.read_csv(MULTI)
    ends["arrival_utc"] = pd.to_datetime(ends["arrival_time_utc"], utc=True)
    if ends.duplicated(["arrival_utc", "arrival_height_m_agl", "hour_back"]).any():
        raise SystemExit("duplicate (arrival, height, hour_back) rows")
    traj500 = tf.per_trajectory(tf.load_endpoints())
    summary["input_checks"] = check_inputs(ends, pd.DatetimeIndex(traj500["date_pkt"]))

    days = pd.read_csv(S7 / "analysis_days.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    centres = pd.read_csv(S7 / "cluster_mean_paths_km.csv", index_col="cluster")
    snpp = ff.prepare(ff.load_source(ff.PRIMARY))
    noaa = ff.prepare(ff.load_source(ff.CROSSCHECK))
    miss_days = aa.missing_satellite_days(snpp, noaa)
    fire_first, fire_last = snpp["date_pkt"].min(), snpp["date_pkt"].max()
    summary["nearest_centre_agreement_500m_pct"] = float(
        100 * (nearest_centre(traj500, centres) == traj500.reset_index()["date_pkt"].map(
            days.set_index("date")["cluster"]).fillna(-1).to_numpy())[traj500["date_pkt"].isin(days["date"]).to_numpy()].mean())

    desc, h1_rows, h1b_rows, h3_rows, null_rows, trajs = [], [], [], [], [], {}
    for h in HEIGHTS:
        tag = f"{int(h)}m"
        eh = ends[ends["arrival_height_m_agl"] == h].copy()
        th = tf.per_trajectory(eh)
        th = th[th["n_points"] == N_POINTS]
        th["cluster_h"] = nearest_centre(th, centres)
        trajs[tag] = th
        per_day = th.reset_index()[["date_pkt", "traj_mean_dist72_km", "cluster_h"]].rename(
            columns={"date_pkt": "date", "traj_mean_dist72_km": f"dist_{tag}"})
        d = days.merge(per_day, on="date", how="inner")

        # 1. descriptive comparison with 500 m
        for s in aa.SEASON_ORDER:
            ds = d[d["season"] == s]
            row = {"height": tag, "season": s, "n_days": len(ds),
                   "median_dist_km": ds[f"dist_{tag}"].median(), "q25_dist_km": ds[f"dist_{tag}"].quantile(.25),
                   "q75_dist_km": ds[f"dist_{tag}"].quantile(.75),
                   "median_dist_500m_km": ds["traj_mean_dist72_km"].median(),
                   "spearman_dist_vs_500m": ds[f"dist_{tag}"].corr(ds["traj_mean_dist72_km"], method="spearman"),
                   "pct_cluster_changed_vs_500m": 100 * (ds["cluster_h"] != ds["cluster"]).mean()}
            for c in sorted(centres.index):
                row[f"pct_C{c}"] = 100 * (ds["cluster_h"] == c).mean()
                row[f"pct_C{c}_500m"] = 100 * (ds["cluster"] == c).mean()
            desc.append(row)

        # 2. H1 (raw and weather-adjusted) and H1b, per season
        dh = d.assign(cluster=d["cluster_h"], traj_mean_dist72_km=d[f"dist_{tag}"])
        for s in aa.SEASON_ORDER:
            ds = dh[dh["season"] == s].sort_values("date")
            for rung, adj in (("raw", None), ("weather_adjusted", ADJUST)):
                r = aa.h1_season(ds, rng, adjust=adj)
                if len(r):
                    h1_rows.append(r.assign(height=tag, season=s, rung=rung))
            ratio, lo, hi, q = aa.h1b_season(ds, rng)
            h1b_rows.append({"height": tag, "season": s, "n_days": len(ds), "tercile_cuts_km": [round(x) for x in q],
                             "ratio_shortest_vs_longest": ratio, "ci_low": lo, "ci_high": hi,
                             "decoupling_rule": decoupling_verdict(ratio, lo, hi)})

        # 3. H3 fire exposure at this height (Stage 7 definition), October-November
        ep = aa.endpoint_table(eh[eh["arrival_utc"].isin(th.index)])
        fe = aa.fire_exposure(ep, snpp)
        miss = aa.exposure_missing_mask(ep, miss_days)
        fe.loc[fe["date"].map(miss).fillna(False).astype(bool), "fe_50km"] = np.nan
        for sh in aa.NULL_SHIFTS:
            fs = aa.fire_exposure(ep, snpp, date_shift_years=sh).rename(columns={"fe_50km": f"fe_null_{sh:+d}"})
            src_dates = fs["date"] - pd.DateOffset(years=sh)
            ok = (src_dates >= fire_first + pd.Timedelta(days=4)) & (src_dates <= fire_last)
            fs.loc[~ok, f"fe_null_{sh:+d}"] = np.nan
            fe = fe.merge(fs, on="date", how="left")
        on = (dh.drop(columns=[c for c in dh.columns if c.startswith("fe_")]).merge(fe, on="date", how="left"))
        on = on[on["season"] == "post-monsoon"].sort_values("date").copy()
        lab, levels, ref = aa.cluster_levels(on)
        on["clab"] = lab
        on["doy_on"] = on["doy"] - 274
        sub = on.dropna(subset=["fe_50km"])
        years = sorted(sub["year"].unique())
        est, lo, hi, _ = aa.fit_with_ci(sub, lambda x, yrs=years: aa.h3_fit(x, "fe_50km", levels, ref, yrs), rng)
        nulls = {}
        for sh in aa.NULL_SHIFTS:
            col = f"fe_null_{sh:+d}"
            sn = on.dropna(subset=[col])
            if len(sn) < 60:
                continue
            nulls[sh] = float(aa.h3_fit(sn, col, levels, ref, sorted(sn["year"].unique()))[0])
            null_rows.append({"height": tag, "shift_years": sh, "c_null": nulls[sh]})
        h3_rows.append({"height": tag, "n_days": len(sub), "c": est[0], "ci_low": lo[0], "ci_high": hi[0],
                        "ratio_per_doubling_of_1plusFE": float(np.exp(est[0] * np.log(2))),
                        "n_null": len(nulls), "null_share_ge_c": float(np.mean([v >= est[0] for v in nulls.values()]))})
        print(f"{tag}: association tests done", flush=True)

    pd.DataFrame(desc).round(3).to_csv(OUT_DIR / "height_comparison.csv", index=False)
    pd.concat(h1_rows).round(3).to_csv(OUT_DIR / "h1_cluster_ratios_by_height.csv", index=False)
    h1b = pd.DataFrame(h1b_rows)
    h1b.round(3).to_csv(OUT_DIR / "h1b_stagnation_by_height.csv", index=False)
    pd.DataFrame(h3_rows).round(4).to_csv(OUT_DIR / "h3_fire_exposure_by_height.csv", index=False)
    pd.DataFrame(null_rows).round(4).to_csv(OUT_DIR / "h3_null_shifts_by_height.csv", index=False)
    summary["decoupling_verdict_winter"] = h1b[h1b["season"] == "winter"].set_index("height")["decoupling_rule"].to_dict()

    # 4. forecasting sensitivity with trajectory features from each height (zero embargo)
    weekly = pd.read_csv(s8.PROC / "pm25_weekly_target.csv", parse_dates=["week_start", "week_end"])
    era5_daily = pd.read_csv(s8.PROC / "era5_daily_pkt.csv", index_col=0, parse_dates=True)
    fire_daily = pd.read_csv(s8.PROC / "firms_viirs_snpp_daily_pkt.csv", index_col=0, parse_dates=True)
    box = mbf.hourly_box(ef.to_hourly_pkt(ef.load_raw()))
    methods = ["persistence", "climatology", "history_model", "rf_L1_history", "rf_L4_plus_massbalance",
               "rf_L5_plus_traj", "rf_L1_plus_traj"]
    comps = [("rf_L5_plus_traj", "rf_L4_plus_massbalance"), ("rf_L1_plus_traj", "rf_L1_history")]
    scores, boots = [], []
    for tag, th in trajs.items():
        p, _ = s8.run(f"forecast_{tag}", weekly, weekly, 0, 1,
                      ["L1_history", "L4_plus_massbalance", "L5_plus_traj", "L1_plus_traj"],
                      traj=th.drop(columns="cluster_h"), era5_daily=era5_daily, fire_daily=fire_daily, box=box)
        p.to_csv(OUT_DIR / f"forecast_predictions_{tag}.csv", index=False, float_format="%.6f")
        scores.append(s4.extended_scores(p, methods).reset_index().assign(height=tag))
        b = s8.bootstrap_table(p, methods, comps).assign(height=tag)
        boots.append(b)
        bl5 = b[(b["model"] == "rf_L5_plus_traj") & (b["subset"] == "all")].iloc[0]
        summary.setdefault("forecast_traj_layer_no_reliable_gain", {})[tag] = bool(bl5["ci95_low"] <= 0 <= bl5["ci95_high"])
    pd.concat(scores).to_csv(OUT_DIR / "forecast_scores_by_height.csv", index=False)
    pd.concat(boots).to_csv(OUT_DIR / "forecast_mae_difference_by_height.csv", index=False)

    (OUT_DIR / "stage9b_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print(h1b.round(3).to_string())


if __name__ == "__main__":
    main()
