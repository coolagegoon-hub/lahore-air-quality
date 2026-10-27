"""Stage 9c: does sharper trajectory meteorology (GDAS 1°) change the trajectories or the results?

Design pre-declared in results/tables/stage9c_gdas_predeclaration.md (approved and committed before any
GDAS file was downloaded). One year (arrivals 2024-03-01 to 2025-02-28) was recomputed on the laptop with
GDAS 1° and is compared, day by day, with the existing NCEP/NCAR 2.5° trajectories. The GDAS trajectories
are a comparison only; the main analysis stays on 2.5° unless the decision rule says otherwise.

Inputs:
    data/raw/hysplit/hysplit_gdas1_out/lahore_backtraj_gdas1_endpoints.csv  (GDAS 1°, 100/250/500 m)
    data/raw/hysplit/lahore_backtraj_endpoints.csv                          (NCEP 2.5°, 500 m)
    data/raw/hysplit/multiheight/lahore_backtraj_multiheight_endpoints.csv  (NCEP 2.5°, 100/250 m)

Choices not spelled out in the pre-declaration (fixed here before any result was seen):
    - cluster agreement (rule a) compares nearest-Stage-7-centre assignments for both GDAS and NCEP, so
      all 365 days use the same rule; agreement of GDAS with the Stage 7 labels on analysis days is
      reported as well;
    - in the five estimates, NCEP uses the Stage 7 labels and Stage 7 fire exposure (the published
      inputs); GDAS uses nearest-centre labels and GDAS fire exposure; a check repeats NCEP with
      nearest-centre labels;
    - "H1: C2/C1 ratio" is the raw ratio of geometric mean PM2.5 on C2 days to C1 days;
    - each estimate uses a fresh generator seeded with 20261025, so NCEP and GDAS draw the same blocks.

Usage:
    python -m src.stage9c_gdas_comparison
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import association_analysis as aa
from src import firms_features as ff
from src import stage9b_multiheight as s9b
from src import trajectory_features as tf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GDAS = PROJECT_ROOT / "data" / "raw" / "hysplit" / "hysplit_gdas1_out" / "lahore_backtraj_gdas1_endpoints.csv"
GDAS_SHA256 = "46b1cd0496f4eabeede3fac6ac1ce27640ecc86f69a9aa99ea63e05048ad8ef7"
S7 = PROJECT_ROOT / "results" / "tables" / "stage7"
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage9c"
FIRST, LAST = pd.Timestamp("2024-03-01"), pd.Timestamp("2025-02-28")
HEIGHTS = (100.0, 250.0, 500.0)
SEP_HOURS = (24, 48, 72)
N_POINTS = 73
N_DAYS = 365
# the five pre-declared estimates: (name, season, season_year)
WINTER = ("winter", 2025)          # Dec 2024 - Feb 2025
POSTMON = ("post-monsoon", 2024)   # Oct - Nov 2024
MIN_CLUSTER_AGREE_PCT = 80.0
MIN_SPEARMAN = 0.8


# ------------------------------------------------------------------ inputs

def load(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d["arrival_utc"] = pd.to_datetime(d["arrival_time_utc"], utc=True)
    if "arrival_height_m_agl" not in d:
        d["arrival_height_m_agl"] = 500.0
    if d.duplicated(["arrival_utc", "arrival_height_m_agl", "hour_back"]).any():
        raise SystemExit(f"duplicate (arrival, height, hour_back) rows in {path.name}")
    day = d["arrival_utc"].dt.tz_convert(tf.TZ).dt.tz_localize(None).dt.normalize()
    return d[(day >= FIRST) & (day <= LAST)].copy()


def check_gdas(g: pd.DataFrame) -> dict:
    n = g.groupby(["arrival_height_m_agl", "arrival_utc"]).size()
    out = {"rows": len(g), "trajectories": int(n.size), "all_73_points": bool((n == N_POINTS).all()),
           "heights": sorted(g["arrival_height_m_agl"].unique().tolist()),
           "arrival_hours_utc": sorted(g["arrival_utc"].dt.hour.unique().tolist()),
           "days": int(g["arrival_utc"].dt.normalize().nunique()),
           "empty_values": int(g.isna().sum().sum())}
    if (out["trajectories"] != N_DAYS * len(HEIGHTS) or not out["all_73_points"] or out["heights"] != list(HEIGHTS)
            or out["arrival_hours_utc"] != [6] or out["days"] != N_DAYS or out["empty_values"]):
        raise SystemExit(f"GDAS input check failed: {out}")
    return out


# ------------------------------------------------------------------ trajectory agreement

def separations(g: pd.DataFrame, n: pd.DataFrame, hours=SEP_HOURS) -> pd.DataFrame:
    """Per trajectory and hour back: great-circle distance between the GDAS and NCEP endpoints, the NCEP
    endpoint's distance from the receptor, and their ratio. Inputs hold one arrival height."""
    key = ["arrival_utc", "hour_back"]
    m = (g[g["hour_back"].isin(hours)][key + ["lat", "lon"]]
         .merge(n[n["hour_back"].isin(hours)][key + ["lat", "lon"]], on=key, suffixes=("_g", "_n")))
    m["sep_km"] = _pairwise_km(m["lat_g"], m["lon_g"], m["lat_n"], m["lon_n"])
    m["ncep_dist_km"], _ = ff.distance_bearing(m["lat_n"], m["lon_n"])
    m["sep_share_of_ncep_dist"] = m["sep_km"] / m["ncep_dist_km"]
    return m


def _pairwise_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(np.asarray(lat1, float)), np.radians(np.asarray(lat2, float))
    dl = np.radians(np.asarray(lon2, float) - np.asarray(lon1, float))
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * ff.EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def agreement(tg: pd.DataFrame, tn: pd.DataFrame, centres: pd.DataFrame) -> pd.DataFrame:
    """Day-level table: transport distance, mean height and nearest-centre cluster from each source."""
    a = pd.DataFrame({"date": tg["date_pkt"].to_numpy(), "dist_g": tg["traj_mean_dist72_km"].to_numpy(),
                      "height_g": tg["traj_mean_height_m"].to_numpy(),
                      "cluster_g": s9b.nearest_centre(tg, centres)})
    b = pd.DataFrame({"date": tn["date_pkt"].to_numpy(), "dist_n": tn["traj_mean_dist72_km"].to_numpy(),
                      "height_n": tn["traj_mean_height_m"].to_numpy(),
                      "cluster_n": s9b.nearest_centre(tn, centres)})
    out = a.merge(b, on="date", how="inner")
    out["season"] = aa.season_of(pd.DatetimeIndex(out["date"]))
    return out


def summarise_agreement(day: pd.DataFrame, sep: pd.DataFrame, height: str) -> list[dict]:
    sep = sep.assign(season=aa.season_of(pd.DatetimeIndex(sep["arrival_utc"].dt.tz_convert(tf.TZ)
                                                          .dt.tz_localize(None).dt.normalize())))
    rows = []
    for s in ["all"] + aa.SEASON_ORDER:
        d = day if s == "all" else day[day["season"] == s]
        e = sep if s == "all" else sep[sep["season"] == s]
        row = {"height": height, "season": s, "n_days": len(d),
               "pct_same_cluster": 100 * (d["cluster_g"] == d["cluster_n"]).mean(),
               "spearman_dist72": d["dist_g"].corr(d["dist_n"], method="spearman"),
               "median_dist72_gdas_km": d["dist_g"].median(), "median_dist72_ncep_km": d["dist_n"].median(),
               "mean_height_gdas_m": d["height_g"].mean(), "mean_height_ncep_m": d["height_n"].mean()}
        for h in SEP_HOURS:
            x = e[e["hour_back"] == h]
            row[f"sep{h}_median_km"] = x["sep_km"].median()
            row[f"sep{h}_q25_km"] = x["sep_km"].quantile(.25)
            row[f"sep{h}_q75_km"] = x["sep_km"].quantile(.75)
            row[f"sep{h}_median_share"] = x["sep_share_of_ncep_dist"].median()
        rows.append(row)
    return rows


# ------------------------------------------------------------------ the five estimates

def pair_ratio(d: pd.DataFrame, num: int = 2, den: int = 1) -> tuple[float, float, float]:
    """Raw ratio of geometric mean PM2.5 on cluster `num` days to cluster `den` days, block-bootstrap CI."""
    dd = d[d["cluster"].isin([num, den])].sort_values("date")

    def build(x):
        a, b = x.loc[x["cluster"] == num, "log_pm"], x.loc[x["cluster"] == den, "log_pm"]
        if not len(a) or not len(b):
            raise ValueError("a cluster is absent from this resample")
        return np.array([a.mean() - b.mean()])

    est, lo, hi, _ = aa.fit_with_ci(dd, build, np.random.default_rng(aa.SEED))
    return float(np.exp(est[0])), float(np.exp(lo[0])), float(np.exp(hi[0]))


def stagnation_ratio(d: pd.DataFrame) -> tuple[float, float, float]:
    r, lo, hi, _ = aa.h1b_season(d.sort_values("date"), np.random.default_rng(aa.SEED))
    return r, lo, hi


def fire_coef(d: pd.DataFrame, fe_col: str = "fe_50km") -> tuple[float, float, float, int]:
    """H3 in one post-monsoon season: log PM ~ log VC + cluster + day of season + c log(1 + FE), no year terms."""
    on = d.sort_values("date").copy()
    lab, levels, ref = aa.cluster_levels(on)
    on["clab"] = lab
    on["doy_on"] = on["doy"] - 274
    sub = on.dropna(subset=[fe_col])
    est, lo, hi, _ = aa.fit_with_ci(sub, lambda x: aa.h3_fit(x, fe_col, levels, ref, []), np.random.default_rng(aa.SEED))
    return float(est[0]), float(lo[0]), float(hi[0]), len(sub)


def estimates(d: pd.DataFrame) -> list[dict]:
    """The five pre-declared estimates on one version of the analysis days (cluster, distance, fe_50km)."""
    w = d[(d["season"] == WINTER[0]) & (d["season_year"] == WINTER[1])]
    p = d[(d["season"] == POSTMON[0]) & (d["season_year"] == POSTMON[1])]
    out = []
    for name, sub in (("H1 C2/C1 winter", w), ("H1 C2/C1 post-monsoon", p)):
        r = pair_ratio(sub)
        out.append({"estimate": name, "n_days": int(sub["cluster"].isin([1, 2]).sum()), "value": r[0],
                    "ci_low": r[1], "ci_high": r[2], "null": 1.0})
    for name, sub in (("H1b shortest/longest winter", w), ("H1b shortest/longest post-monsoon", p)):
        r = stagnation_ratio(sub)
        out.append({"estimate": name, "n_days": len(sub), "value": r[0], "ci_low": r[1], "ci_high": r[2], "null": 1.0})
    c, lo, hi, n = fire_coef(p)
    out.append({"estimate": "H3 fire coefficient c Oct-Nov 2024", "n_days": n, "value": c, "ci_low": lo, "ci_high": hi,
                "null": 0.0})
    return out


def rule_c(ncep: pd.DataFrame, gdas: pd.DataFrame) -> pd.DataFrame:
    m = ncep.merge(gdas, on=["estimate", "null"], suffixes=("_ncep", "_gdas"))
    m["gdas_outside_ncep_ci"] = (m["value_gdas"] < m["ci_low_ncep"]) | (m["value_gdas"] > m["ci_high_ncep"])
    m["opposite_sides_of_null"] = np.sign(m["value_ncep"] - m["null"]) * np.sign(m["value_gdas"] - m["null"]) < 0
    m["triggers"] = m["gdas_outside_ncep_ci"] | m["opposite_sides_of_null"]
    return m


def decision(pct_same: float, rho: float, c_table: pd.DataFrame) -> dict:
    a, b, c = pct_same < MIN_CLUSTER_AGREE_PCT, rho < MIN_SPEARMAN, bool(c_table["triggers"].any())
    return {"a_cluster_agreement_below_80pct": bool(a), "b_spearman_below_0.8": bool(b),
            "c_any_estimate_moved": c, "changes_substantially": bool(a or b or c)}


# ------------------------------------------------------------------ main

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"predeclaration": "results/tables/stage9c_gdas_predeclaration.md"}
    digest = s9b.sha256(GDAS)
    summary["gdas_sha256"] = digest
    if digest != GDAS_SHA256:
        raise SystemExit(f"SHA-256 mismatch: {digest}")
    g_all = load(GDAS)
    summary["gdas_checks"] = check_gdas(g_all)
    n500 = load(tf.ENDPOINTS)
    nmulti = load(s9b.MULTI)
    ncep = {500.0: n500, **{h: nmulti[nmulti["arrival_height_m_agl"] == h] for h in (100.0, 250.0)}}
    centres = pd.read_csv(S7 / "cluster_mean_paths_km.csv", index_col="cluster")

    # 1. trajectory agreement, all three heights
    rows, day500, tg500 = [], None, None
    for h in HEIGHTS:
        g, n = g_all[g_all["arrival_height_m_agl"] == h], ncep[h]
        tg, tn = tf.per_trajectory(g), tf.per_trajectory(n)
        if len(tn) != N_DAYS or (tn["n_points"] != N_POINTS).any():
            raise SystemExit(f"NCEP {h} m set incomplete for the year: {len(tn)} trajectories")
        day = agreement(tg, tn, centres)
        rows += summarise_agreement(day, separations(g, n), f"{int(h)}m")
        if h == 500.0:
            day500, tg500 = day, tg
    agree = pd.DataFrame(rows)
    agree.round(3).to_csv(OUT_DIR / "trajectory_agreement.csv", index=False)
    a500 = agree[(agree["height"] == "500m") & (agree["season"] == "all")].iloc[0]

    # 2. the five estimates on the year's analysis days, 500 m
    days = pd.read_csv(S7 / "analysis_days.csv", parse_dates=["date"])
    days = days[(days["date"] >= FIRST) & (days["date"] <= LAST)].sort_values("date").reset_index(drop=True)
    m = days.merge(day500[["date", "cluster_g", "cluster_n", "dist_g"]], on="date", how="left")
    summary["analysis_days"] = len(m)
    summary["pct_gdas_same_as_stage7_label_analysis_days"] = float(100 * (m["cluster_g"] == m["cluster"]).mean())
    summary["pct_ncep_nearest_same_as_stage7_label_analysis_days"] = float(100 * (m["cluster_n"] == m["cluster"]).mean())

    snpp = ff.prepare(ff.load_source(ff.PRIMARY))
    noaa = ff.prepare(ff.load_source(ff.CROSSCHECK))
    ep = aa.endpoint_table(g_all[g_all["arrival_height_m_agl"] == 500.0])
    fe = aa.fire_exposure(ep, snpp)
    miss = aa.exposure_missing_mask(ep, aa.missing_satellite_days(snpp, noaa))
    fe.loc[fe["date"].map(miss).fillna(False).astype(bool), "fe_50km"] = np.nan
    gd = (m.drop(columns=["fe_50km"]).merge(fe[["date", "fe_50km"]], on="date", how="left")
          .assign(cluster=m["cluster_g"], traj_mean_dist72_km=m["dist_g"]))

    est_n = pd.DataFrame(estimates(m))
    est_g = pd.DataFrame(estimates(gd))
    est_nc = pd.DataFrame(estimates(m.assign(cluster=m["cluster_n"])))
    ct = rule_c(est_n, est_g)
    ct_check = rule_c(est_nc, est_g)
    ct.round(4).to_csv(OUT_DIR / "estimates_ncep_vs_gdas.csv", index=False)
    ct_check.round(4).to_csv(OUT_DIR / "estimates_check_ncep_nearest_centre.csv", index=False)

    summary["rule_inputs_500m_all_days"] = {"pct_same_cluster": float(a500["pct_same_cluster"]),
                                            "spearman_dist72": float(a500["spearman_dist72"])}
    summary["decision"] = decision(a500["pct_same_cluster"], a500["spearman_dist72"], ct)
    summary["decision_check_ncep_nearest_centre"] = decision(a500["pct_same_cluster"], a500["spearman_dist72"], ct_check)
    (OUT_DIR / "stage9c_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print(agree[agree["season"].isin(["all", "winter", "post-monsoon"])].round(2).to_string())
    print(ct.round(3).to_string())
    print(ct_check.round(3).to_string())


if __name__ == "__main__":
    main()
