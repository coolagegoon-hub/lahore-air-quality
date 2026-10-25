"""Stage 8: one-week embargo, sensitivity runs, SHAP stability, diagnostic (target-week) models and
the weekly ventilation slope.

Design pre-declared in results/tables/stage8_predeclaration.md (committed 060cccd before any Stage 8
code was run). Everything not listed there is unchanged from Stages 3–6.

One engine covers every run. For target week T:
- ``embargo`` (weeks, 0 or 1): data are treated as available only before C = T − 7·embargo days.
  PM2.5 history, persistence, climatology and training targets must end before C.
- ``cond_lag`` (weeks): ERA5, FIRMS, mass-balance and trajectory features describe week T − cond_lag
  (1 = forecast as in Stages 3–6, 2 = one-week embargo, 0 = diagnostic, target week itself).
With embargo = 0 and cond_lag = 1 the engine must reproduce Stages 2–4 exactly (checked in main()).

Usage (after Stages 2–6):
    python -m src.stage8_robustness
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import shap
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import airnow_hourly_series as ahs
from src import baselines as bl
from src import era5_features as ef
from src import firms_features as ff
from src import history_model as hm
from src import main_model as mm
from src import mass_balance_features as mbf
from src import shap_analysis as sa
from src import stage2_weekly as s2
from src import stage4_trajectory_model as s4
from src import trajectory_features as tf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROC = PROJECT_ROOT / "data" / "processed"
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage8"
WEEK = pd.Timedelta(days=7)
SLOPE_SEED = 20261025
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "pre-monsoon", 4: "pre-monsoon", 5: "pre-monsoon",
           6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon", 10: "post-monsoon", 11: "post-monsoon"}
TOL = 1e-6


# ------------------------------------------------------------------ inputs

def history_features(weekly: pd.DataFrame, targets, embargo: int) -> pd.DataFrame:
    """src.history_model features computed at C = T − 7·embargo; age measured from T, calendar of T."""
    targets = pd.DatetimeIndex(targets)
    f = hm.features_for_targets(weekly, targets - embargo * WEEK)
    f["target_week_start"] = targets
    f["age_last"] = f["age_last"] + embargo
    ang = 2 * np.pi * (targets + pd.Timedelta(days=3)).day_of_year.to_numpy() / 365.25
    f["sin1"], f["cos1"], f["sin2"], f["cos2"] = np.sin(ang), np.cos(ang), np.sin(2 * ang), np.cos(2 * ang)
    return f


def condition_features(targets, cond_lag: int, era5_daily: pd.DataFrame, fire_daily: pd.DataFrame,
                       box: pd.DataFrame) -> pd.DataFrame:
    """ERA5, FIRMS and mass-balance features of week T − cond_lag (the builders use week T'−1)."""
    targets = pd.DatetimeIndex(targets)
    shifted = targets - (cond_lag - 1) * WEEK
    parts = [ef.previous_week_features(era5_daily, shifted), ff.previous_week_features(fire_daily, shifted),
             mbf.previous_week_features(box, shifted)]
    out = pd.DataFrame({"target_week_start": targets})
    for p in parts:
        p = p.copy()
        p["target_week_start"] = targets
        out = out.merge(p, on="target_week_start", how="left")
    return out


def build_table(weekly_inputs: pd.DataFrame, weekly_target: pd.DataFrame, embargo: int, cond_lag: int,
                era5_daily, fire_daily, box) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """One row per week (as src.main_model.load_feature_table): target and eligibility from
    ``weekly_target``; PM2.5 history from ``weekly_inputs``."""
    starts = weekly_target["week_start"]
    hist = history_features(weekly_inputs, starts, embargo)
    hist = hist.loc[hist["reason"].eq("ok")].drop(columns="reason")
    cond = condition_features(starts, cond_lag, era5_daily, fire_daily, box)
    t = weekly_target.rename(columns={"week_start": "target_week_start"})[
        ["target_week_start", "week_end", "weekly_mean_observed_days", "eligible", "partial_week"]]
    t = t.merge(hist, on="target_week_start", how="left").merge(cond, on="target_week_start", how="left")
    t["smog_season_week"] = (t["target_week_start"] + pd.Timedelta(days=3)).dt.month.isin(mm.SMOG_MONTHS)
    era5 = [c for c in cond.columns if c.startswith("era5_prev_")]
    fire = [c for c in cond.columns if c.startswith("fire_prev_")]
    mass = [c for c in cond.columns if c.startswith("mb_prev_")]
    h = list(hm.FEATURES)
    layers = {"L1_history": h, "L2_plus_era5": h + era5, "L3_plus_fire": h + era5 + fire,
              "L4_plus_massbalance": h + era5 + fire + mass}
    return t.sort_values("target_week_start", ignore_index=True), layers


# ------------------------------------------------------------------ models

def baselines(weekly_inputs: pd.DataFrame, targets, embargo: int) -> pd.DataFrame:
    """Persistence and climatology with inputs ending before C = T − 7·embargo."""
    w = bl._validate_weekly(weekly_inputs)
    rows = []
    for t in sorted({bl.issuance_cutoff(x) for x in targets}):
        past = w.loc[w["week_end"] < t - embargo * WEEK]
        p = bl.persistence(past, t)
        c = bl.seasonal_climatology(past, t, **s2.CLIMATOLOGY_KWARGS)
        rows.append({"target_week_start": t, "persistence": p["prediction"], "climatology": c["prediction"]})
    return pd.DataFrame(rows)


def ridge_history(table: pd.DataFrame, targets, embargo: int) -> pd.DataFrame:
    """src.history_model's Ridge (log target, smearing) on the table's history features."""
    feats = list(hm.FEATURES)
    t = table.set_index("target_week_start")
    usable = t[feats].notna().all(axis=1)
    y = np.log(t["weekly_mean_observed_days"].where(t["eligible"]))
    out = []
    for tgt in sorted({bl.issuance_cutoff(x) for x in targets}):
        rec = {"target_week_start": tgt, "history_model": np.nan}
        if tgt in t.index and usable.get(tgt, False):
            train = t[(t["week_end"] < tgt - embargo * WEEK) & y.notna() & usable]
            if len(train) >= hm.MIN_TRAIN_ROWS:
                model = make_pipeline(StandardScaler(), Ridge(alpha=hm.RIDGE_ALPHA))
                X, yy = train[feats].to_numpy(float), y[train.index].to_numpy(float)
                model.fit(X, yy)
                smear = float(np.mean(np.exp(yy - model.predict(X))))
                rec["history_model"] = float(np.exp(model.predict(t.loc[[tgt], feats].to_numpy(float))[0]) * smear)
        out.append(rec)
    return pd.DataFrame(out)


def walk_forward_rf(table: pd.DataFrame, features: list[str], targets, embargo: int) -> pd.DataFrame:
    """src.main_model.walk_forward_rf with training targets ending before C."""
    usable = table[features].notna().all(axis=1)
    out = []
    for tgt in sorted({bl.issuance_cutoff(x) for x in targets}):
        rec = {"target_week_start": tgt, "pred": np.nan}
        f = table.loc[table["target_week_start"].eq(tgt)]
        if not f.empty and usable.loc[f.index].iloc[0]:
            train = table[(table["week_end"] < tgt - embargo * WEEK) & table["eligible"] & usable]
            if len(train) >= mm.MIN_TRAIN_ROWS:
                model = RandomForestRegressor(**mm.RF_PARAMS)
                model.fit(train[features].to_numpy(float), train["weekly_mean_observed_days"].to_numpy(float))
                rec["pred"] = float(model.predict(f[features].to_numpy(float))[0])
        out.append(rec)
    return pd.DataFrame(out)


def traj_weekly(traj: pd.DataFrame, cond_lag: int) -> pd.DataFrame:
    """Continuous trajectory features per target week T from the trajectories of week T − cond_lag."""
    t = traj.copy()
    t["target_week_start"] = tf.week_start(t["date_pkt"]) + cond_lag * WEEK
    g = t.groupby("target_week_start")
    w = g[tf.CONT_FEATURES].mean()
    w.loc[g.size() < tf.MIN_TRAJ_PER_WEEK, tf.CONT_FEATURES] = np.nan
    return w


def traj_fractions(traj: pd.DataFrame, km, assign_before: pd.Timestamp, cond_lag: int, k: int) -> pd.DataFrame:
    use = traj[traj["date_pkt"] < assign_before]
    labels = km.predict(use[tf.shape_columns()].to_numpy(float))
    onehot = pd.DataFrame(np.eye(k)[labels], index=use.index, columns=[f"traj_frac_c{i + 1}" for i in range(k)])
    onehot["target_week_start"] = tf.week_start(use["date_pkt"]) + cond_lag * WEEK
    g = onehot.groupby("target_week_start")
    fr = g.mean()
    fr.loc[g.size() < tf.MIN_TRAJ_PER_WEEK, :] = np.nan
    return fr


def walk_forward_traj(table: pd.DataFrame, base_features: list[str], targets, traj: pd.DataFrame,
                      embargo: int, cond_lag: int, k: int = tf.N_CLUSTERS, with_shap: bool = False):
    """src.stage4_trajectory_model.walk_forward_traj generalised: k-means fitted on trajectories before
    C − 7 d; trajectories before T − 7·(cond_lag − 1) are assigned; training targets end before C.
    Returns predictions and (if with_shap) one row of test-row SHAP values per forecast."""
    cont = traj_weekly(traj, cond_lag)
    feats = base_features + [f"traj_frac_c{i + 1}" for i in range(k)] + tf.CONT_FEATURES
    base = table.set_index("target_week_start")
    out, rows = [], []
    for tgt in sorted({bl.issuance_cutoff(x) for x in targets}):
        rec = {"target_week_start": tgt, "pred": np.nan}
        out.append(rec)
        c = tgt - embargo * WEEK
        km = tf.fit_fold_clusters(traj, c, k=k)        # fits on trajectories before c − 7 d
        if km is None:
            continue
        fr = traj_fractions(traj, km, tgt - (cond_lag - 1) * WEEK, cond_lag, k)
        t = base.loc[:tgt].join(fr, how="left").join(cont[tf.CONT_FEATURES], how="left")
        usable = t[feats].notna().all(axis=1)
        if tgt not in t.index or not usable.get(tgt, False):
            continue
        train = t[(t["week_end"] < c) & t["eligible"] & usable]
        if len(train) < mm.MIN_TRAIN_ROWS:
            continue
        model = RandomForestRegressor(**mm.RF_PARAMS)
        model.fit(train[feats].to_numpy(float), train["weekly_mean_observed_days"].to_numpy(float))
        x = t.loc[[tgt], feats].to_numpy(float)
        rec["pred"] = float(model.predict(x)[0])
        if with_shap:
            ex = shap.TreeExplainer(model)
            sv = np.asarray(ex.shap_values(x))[0]
            rows.append({"target_week_start": tgt, "base_value": float(np.ravel(ex.expected_value)[0]),
                         "prediction": rec["pred"], **dict(zip(feats, sv))})
    return pd.DataFrame(out), pd.DataFrame(rows)


# ------------------------------------------------------------------ one run

def run(name: str, weekly_inputs, weekly_target, embargo: int, cond_lag: int, models: list[str], traj,
        era5_daily, fire_daily, box, with_shap: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    table, layers = build_table(weekly_inputs, weekly_target, embargo, cond_lag, era5_daily, fire_daily, box)
    targets = table.loc[~table["partial_week"], "target_week_start"]
    preds = baselines(weekly_inputs, targets, embargo)
    preds = preds.merge(ridge_history(table, targets, embargo), on="target_week_start", how="left")
    shap_rows = pd.DataFrame()
    for m in models:
        if m in layers:
            p = walk_forward_rf(table, layers[m], targets, embargo)
        else:
            base = layers["L1_history"] if m == "L1_plus_traj" else layers["L4_plus_massbalance"]
            p, sv = walk_forward_traj(table, base, targets, traj, embargo, cond_lag,
                                      with_shap=with_shap and m == "L5_plus_traj")
            if len(sv):
                shap_rows = sv
        preds = preds.merge(p.rename(columns={"pred": f"rf_{m}"}), on="target_week_start", how="left")
        print(f"  {name}: rf_{m} done", flush=True)
    truth = weekly_target.set_index("week_start")
    preds["observed"] = preds["target_week_start"].map(truth["weekly_mean_observed_days"])
    preds["observed_eligible"] = preds["target_week_start"].map(truth["eligible"]).astype(bool)
    preds["smog_season_week"] = (preds["target_week_start"] + pd.Timedelta(days=3)).dt.month.isin(mm.SMOG_MONTHS)
    return preds, shap_rows


def common_errors(preds: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    e = preds[preds["observed_eligible"].eq(True)]
    return e.loc[e[methods].notna().all(axis=1)].sort_values("target_week_start")


def bootstrap_table(preds: pd.DataFrame, methods: list[str], comps) -> pd.DataFrame:
    c = common_errors(preds, methods)
    obs = c["observed"].to_numpy(float)
    smog = c["smog_season_week"].to_numpy()
    rows = []
    for a, b in comps:
        ea, eb = c[a].to_numpy(float) - obs, c[b].to_numpy(float) - obs
        for subset, mask in (("all", np.ones(len(c), bool)), ("smog", smog)):
            rows.append({"model": a, "compared_to": b, "subset": subset, "n": int(mask.sum()),
                         **mm.block_bootstrap_mae_diff(ea[mask], eb[mask])})
    return pd.DataFrame(rows).round(3)


# ------------------------------------------------------------------ SHAP and slope

def shap_summary(sv: pd.DataFrame, preds: pd.DataFrame, methods: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    feats = [c for c in sv.columns if c not in ("target_week_start", "base_value", "prediction")]
    groups = sa.feature_groups(feats)
    common = set(common_errors(preds, methods)["target_week_start"])
    s = sv[sv["target_week_start"].isin(common)].reset_index(drop=True)
    summ = sa.group_summary(s, groups, {"all": pd.Series(True, index=s.index)})
    clusters = [f"traj_frac_c{i + 1}" for i in range(tf.N_CLUSTERS)]
    top = sa.top_features(s, feats, clusters)
    return summ, top


def stability(summ: pd.DataFrame, top: pd.DataFrame, main_summ: pd.DataFrame, main_top: pd.DataFrame) -> dict:
    a = summ.set_index("group")["share_pct"]
    b = main_summ.set_index("group")["share_pct"].reindex(a.index)
    rho = float(spearmanr(a, b).statistic)
    top2, main_top2 = set(a.nlargest(2).index), set(b.nlargest(2).index)
    overlap = len(set(top["feature"]) & set(main_top["feature"]))
    return {"spearman_family_shares": round(rho, 3), "top2_families": sorted(top2),
            "top2_same_as_main": top2 == main_top2, "top10_feature_overlap": overlap,
            "stable": bool(top2 == main_top2 and rho >= 0.8), "shares_pct": a.round(1).to_dict()}


def ols_slope(x: np.ndarray, y: np.ndarray) -> float:
    xc = x - x.mean()
    return float((xc * (y - y.mean())).sum() / (xc ** 2).sum())


def block_bootstrap_slope(x: np.ndarray, y: np.ndarray, block: int = 4, n_boot: int = mm.N_BOOT,
                          seed: int = SLOPE_SEED) -> tuple[float, float]:
    n = len(x)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, max(n - block + 1, 1), size=(n_boot, int(np.ceil(n / block))))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    xb, yb = x[idx], y[idx]
    xc = xb - xb.mean(axis=1, keepdims=True)
    slopes = (xc * (yb - yb.mean(axis=1, keepdims=True))).sum(axis=1) / (xc ** 2).sum(axis=1)
    return float(np.quantile(slopes, 0.025)), float(np.quantile(slopes, 0.975))


def weekly_ventilation_slopes(weekly: pd.DataFrame, box: pd.DataFrame) -> pd.DataFrame:
    w = weekly[weekly["eligible"] & ~weekly["partial_week"]].copy()
    same = mbf.previous_week_features(box, w["week_start"] + WEEK)        # hours of week T itself
    w["vc"] = same["mb_prev_vc_mean"].to_numpy()
    w = w[w["vc"].notna()].sort_values("week_start")
    w["season"] = (w["week_start"] + pd.Timedelta(days=3)).dt.month.map(SEASONS)
    rows = []
    for s in ("winter", "pre-monsoon", "monsoon", "post-monsoon"):
        d = w[w["season"] == s]
        x, y = np.log(d["vc"].to_numpy(float)), np.log(d["weekly_mean_observed_days"].to_numpy(float))
        lo, hi = block_bootstrap_slope(x, y)
        rows.append({"season": s, "n_weeks": len(d), "slope": ols_slope(x, y), "ci95_low": lo, "ci95_high": hi})
    return pd.DataFrame(rows).round(3)


# ------------------------------------------------------------------ targets for S1–S4

def weekly_airnow_daily() -> pd.DataFrame:
    """S1: weekly targets from AirNow's own daily values (a day is valid if AirNow reports a value)."""
    d = pd.read_csv(PROC / "airnow_586PK3010003_daily.csv", parse_dates=["date"])
    d = d[d["parameter"].eq("PM2.5-24hr")].drop_duplicates("date", keep="last")
    daily = pd.DataFrame({"date": d["date"], "hours_valid": 24, "pm25_daily_mean": d["value"]}).set_index("date")
    return s2.weekly_from_daily(daily)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    weekly = pd.read_csv(PROC / "pm25_weekly_target.csv", parse_dates=["week_start", "week_end"])
    era5_daily = pd.read_csv(PROC / "era5_daily_pkt.csv", index_col=0, parse_dates=True)
    fire_daily = pd.read_csv(PROC / "firms_viirs_snpp_daily_pkt.csv", index_col=0, parse_dates=True)
    box = mbf.hourly_box(ef.to_hourly_pkt(ef.load_raw()))
    traj = tf.per_trajectory(tf.load_endpoints())
    args = dict(traj=traj, era5_daily=era5_daily, fire_daily=fire_daily, box=box)
    summary = {"predeclaration": "results/tables/stage8_predeclaration.md"}

    # 0. Reproduction check: embargo 0, cond_lag 1 must equal Stages 2–4.
    ref, _ = run("check", weekly, weekly, 0, 1, ["L4_plus_massbalance", "L5_plus_traj"], **args)
    old = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage4" / "predictions_all_models.csv",
                      parse_dates=["target_week_start"])
    m = ref.merge(old, on="target_week_start", suffixes=("", "_old"))
    errs = {c: float((m[c] - m[f"{c}_old"]).abs().max())
            for c in ["persistence", "climatology", "history_model", "rf_L4_plus_massbalance", "rf_L5_plus_traj"]}
    print("reproduction max abs error:", errs, flush=True)
    if max(errs.values()) > 1e-4 or m["rf_L5_plus_traj"].notna().sum() != m["rf_L5_plus_traj_old"].notna().sum():
        raise SystemExit(f"reproduction check failed: {errs}")
    summary["reproduction_max_abs_error"] = errs
    main_methods = ["persistence", "climatology", "history_model", "rf_L4_plus_massbalance", "rf_L5_plus_traj"]

    # 1. One-week embargo.
    emb_models = ["L1_history", "L2_plus_era5", "L3_plus_fire", "L4_plus_massbalance", "L5_plus_traj", "L1_plus_traj"]
    emb, emb_sv = run("embargo", weekly, weekly, 1, 2, emb_models, with_shap=True, **args)
    emb.to_csv(OUT_DIR / "embargo_predictions.csv", index=False, float_format="%.6f")
    emb_methods = ["persistence", "climatology", "history_model"] + [f"rf_{x}" for x in emb_models]
    s4.extended_scores(emb, emb_methods).to_csv(OUT_DIR / "embargo_scores_common_set.csv")
    comps = [("rf_L2_plus_era5", "rf_L1_history"), ("rf_L3_plus_fire", "rf_L2_plus_era5"),
             ("rf_L4_plus_massbalance", "rf_L3_plus_fire"), ("rf_L5_plus_traj", "rf_L4_plus_massbalance"),
             ("rf_L1_plus_traj", "rf_L1_history"), ("rf_L5_plus_traj", "history_model"),
             ("rf_L5_plus_traj", "climatology"), ("rf_L5_plus_traj", "persistence")]
    bootstrap_table(emb, emb_methods, comps).to_csv(OUT_DIR / "embargo_mae_difference_bootstrap.csv", index=False)

    # cost of the embargo: same method, embargo vs zero embargo, weeks where both forecast
    zero = old       # Stage 4 file holds every zero-embargo forecast (Stages 2–4)
    cost = []
    for meth in ["persistence", "climatology", "history_model", "rf_L1_history", "rf_L2_plus_era5", "rf_L3_plus_fire",
                 "rf_L4_plus_massbalance", "rf_L5_plus_traj", "rf_L1_plus_traj"]:
        j = emb[["target_week_start", "observed", "observed_eligible", "smog_season_week", meth]].merge(
            zero[["target_week_start", meth]], on="target_week_start", suffixes=("_emb", "_zero"))
        j = j[j["observed_eligible"] & j[f"{meth}_emb"].notna() & j[f"{meth}_zero"].notna()].sort_values("target_week_start")
        obs = j["observed"].to_numpy(float)
        for subset, mask in (("all", np.ones(len(j), bool)), ("smog", j["smog_season_week"].to_numpy())):
            ea, ez = j[f"{meth}_emb"].to_numpy(float)[mask] - obs[mask], j[f"{meth}_zero"].to_numpy(float)[mask] - obs[mask]
            cost.append({"method": meth, "subset": subset, "n": int(mask.sum()), "mae_embargo": mm.mae(ea),
                         "mae_zero": mm.mae(ez), **mm.block_bootstrap_mae_diff(ea, ez)})
    pd.DataFrame(cost).round(3).to_csv(OUT_DIR / "embargo_cost_vs_zero.csv", index=False)

    # 2. Sensitivity runs S1–S4 (zero embargo) with SHAP for L5.
    grid = ahs.load_saved_grid()
    daily7, _ = s2.final_daily(grid)
    daily6, excl6 = s2.final_daily(grid, run_rule_hours=6)
    s4_target = weekly.copy()
    s4_target.loc[(s4_target["week_start"] + pd.Timedelta(days=3)).dt.year.isin([2020, 2021]), "eligible"] = False
    sens = {"S1_airnow_daily": (weekly_airnow_daily(),) * 2,
            "S2_complete_7_of_7": (s2.weekly_from_daily(daily7, 7),) * 2,
            "S3_run_rule_6h": (s2.weekly_from_daily(daily6),) * 2,
            "S4_exclude_2020_2021": (weekly, s4_target)}
    summary["S3_hours_excluded_by_run_rule"] = excl6
    sens_comps = [("rf_L5_plus_traj", "rf_L4_plus_massbalance"), ("rf_L5_plus_traj", "history_model"),
                  ("rf_L5_plus_traj", "climatology"), ("rf_L5_plus_traj", "persistence")]
    shap_runs = {"embargo": (emb_sv, emb, emb_methods)}
    sens_rows, sens_boot = [], []
    for name, (w_in, w_tg) in sens.items():
        p, sv = run(name, w_in, w_tg, 0, 1, ["L4_plus_massbalance", "L5_plus_traj"], with_shap=True, **args)
        p.to_csv(OUT_DIR / f"{name}_predictions.csv", index=False, float_format="%.6f")
        sc = s4.extended_scores(p, main_methods).reset_index().assign(run=name)
        sens_rows.append(sc)
        b = bootstrap_table(p, main_methods, sens_comps).assign(run=name)
        sens_boot.append(b)
        shap_runs[name] = (sv, p, main_methods)
        summary.setdefault("sensitivity_eligible_weeks", {})[name] = int((w_tg["eligible"] & ~w_tg["partial_week"]).sum())
    pd.concat(sens_rows).to_csv(OUT_DIR / "sensitivity_scores_common_set.csv", index=False)
    sb = pd.concat(sens_boot)
    sb.to_csv(OUT_DIR / "sensitivity_mae_difference_bootstrap.csv", index=False)
    agree = {}
    for name in sens:
        b = sb[(sb["run"] == name) & (sb["subset"] == "all")].set_index("compared_to")
        crit = {"L5_vs_L4_interval_includes_0": bool(b.loc["rf_L4_plus_massbalance", "ci95_low"] <= 0 <= b.loc["rf_L4_plus_massbalance", "ci95_high"]),
                "L5_better_than_persistence": bool(b.loc["persistence", "ci95_high"] < 0),
                "L5_vs_ridge_interval_includes_0": bool(b.loc["history_model", "ci95_low"] <= 0 <= b.loc["history_model", "ci95_high"])}
        agree[name] = {**crit, "agrees_with_main": all(crit.values())}
    summary["sensitivity_agreement"] = agree

    # 3. SHAP stability vs Stage 5.
    main_summ = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage5" / "shap_group_summary.csv")
    main_summ = main_summ[main_summ["subset"] == "all"]
    main_top = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage5" / "shap_top_features_all.csv")
    stab, shares = {}, []
    for name, (sv, p, meths) in shap_runs.items():
        feats = [c for c in sv.columns if c not in ("target_week_start", "base_value", "prediction")]
        add_err = float((sv["base_value"] + sv[feats].sum(axis=1) - sv["prediction"]).abs().max())
        if add_err > TOL:
            raise SystemExit(f"SHAP additivity failed in {name}: {add_err}")
        summ, top = shap_summary(sv, p, meths)
        stab[name] = {**stability(summ, top, main_summ, main_top), "n_weeks": int(summ["n_weeks"].iloc[0]),
                      "additivity_max_error": add_err}
        shares.append(summ.assign(run=name))
        top.assign(run=name).to_csv(OUT_DIR / f"shap_top_features_{name}.csv", index=False)
    pd.concat(shares).round(3).to_csv(OUT_DIR / "shap_group_shares_by_run.csv", index=False)
    summary["shap_stability"] = stab
    summary["H5_shap_stable_in_every_run"] = all(v["stable"] for v in stab.values())

    # 4. Diagnostic (target-week conditions; NOT a forecast).
    diag, _ = run("diagnostic", weekly, weekly, 0, 0, ["L4_plus_massbalance", "L5_plus_traj"], **args)
    diag = diag.rename(columns={"rf_L4_plus_massbalance": "diag_L4", "rf_L5_plus_traj": "diag_L5"})
    diag = diag.merge(old[["target_week_start", "rf_L5_plus_traj"]], on="target_week_start", how="left")
    diag.to_csv(OUT_DIR / "diagnostic_predictions.csv", index=False, float_format="%.6f")
    dm = ["persistence", "rf_L5_plus_traj", "diag_L4", "diag_L5"]
    s4.extended_scores(diag, dm).to_csv(OUT_DIR / "diagnostic_scores_common_set.csv")
    bootstrap_table(diag, dm, [("diag_L5", "rf_L5_plus_traj"), ("diag_L4", "rf_L5_plus_traj")]).to_csv(
        OUT_DIR / "diagnostic_mae_difference_bootstrap.csv", index=False)

    # 5. Weekly ventilation slope.
    slopes = weekly_ventilation_slopes(weekly, box)
    slopes.to_csv(OUT_DIR / "weekly_ventilation_slopes.csv", index=False)

    for n, (meths, p) in {"embargo": (emb_methods, emb), "diagnostic": (dm, diag)}.items():
        c = common_errors(p, meths)
        summary[f"{n}_common_weeks"] = int(len(c))
        summary[f"{n}_common_smog_weeks"] = int(c["smog_season_week"].sum())
        summary[f"{n}_common_span"] = [str(c["target_week_start"].min().date()), str(c["target_week_start"].max().date())]
    (OUT_DIR / "stage8_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print(slopes.to_string())


if __name__ == "__main__":
    main()
