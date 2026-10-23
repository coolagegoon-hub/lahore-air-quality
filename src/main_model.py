"""Stage 3: main machine-learning model (Random Forest), walk-forward, built up in input layers.

Research question (CLAUDE.md): do ERA5 meteorology, NASA FIRMS fire activity and one-box
mass-balance features improve weekly PM2.5 forecasts beyond historical PM2.5? (HYSPLIT trajectories
are added as layer L5 in src.stage4_trajectory_model.)

Design (fixed before any results were seen; nothing tuned on the evaluation period):
- Target: weekly mean PM2.5 (µg/m³), eligible weeks only (>= 6 of 7 valid days), from
  data/processed/pm25_weekly_target.csv (AirNow, AQS 586PK3010003; preliminary data).
- Forecast for week T issued Monday 00:00 PKT. Every feature uses only data before that cutoff:
  history features (src.history_model.features_for_targets) and previous-week ERA5, FIRMS and
  mass-balance features (src.era5_features, src.firms_features, src.mass_balance_features).
- Feature layers (cumulative):
    L1_history            history features only
    L2_plus_era5          + ERA5 previous-week weather
    L3_plus_fire          + FIRMS previous-week fires
    L4_plus_massbalance   + one-box mass-balance features
- Model: scikit-learn RandomForestRegressor with fixed settings RF_PARAMS (random_state fixed),
  trained on the raw weekly mean (no transform). Refitted from scratch for every target week on
  rows whose target week ended before T's cutoff (expanding window), requiring >= MIN_TRAIN_ROWS
  training rows. No scaling or other preprocessing is fitted (trees do not need it).
- Rows with any missing feature are neither trained on nor predicted (no imputation).
- Scoring: on eligible observed weeks where EVERY compared method has a prediction (common set),
  overall and by smog season (Oct–Jan by the week's Thursday). Uncertainty of MAE differences:
  paired moving-block bootstrap over weeks (BLOCK_WEEKS, N_BOOT, fixed seed).

Usage (after src.stage2_weekly, src.history_model and the three feature scripts):
    python -m src.main_model
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from src import baselines as bl
from src import history_model as hm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROC = PROJECT_ROOT / "data" / "processed"
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage3"
SEED = 20261021
RF_PARAMS = {"n_estimators": 300, "min_samples_leaf": 5, "max_features": 0.33, "random_state": SEED, "n_jobs": -1}
MIN_TRAIN_ROWS = 52
BLOCK_WEEKS = 4
N_BOOT = 2000
SMOG_MONTHS = (10, 11, 12, 1)


def load_feature_table() -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """One row per week: target, eligibility and all features keyed by target_week_start."""
    weekly = pd.read_csv(PROC / "pm25_weekly_target.csv", parse_dates=["week_start", "week_end"])
    hist = hm.features_for_targets(weekly, weekly["week_start"])
    hist = hist.loc[hist["reason"].eq("ok")].drop(columns="reason")
    era5 = pd.read_csv(PROC / "era5_prev_week_features.csv", parse_dates=["target_week_start"])
    fire = pd.read_csv(PROC / "firms_prev_week_features.csv", parse_dates=["target_week_start"])
    mbf = pd.read_csv(PROC / "mass_balance_prev_week_features.csv", parse_dates=["target_week_start"])
    t = weekly.rename(columns={"week_start": "target_week_start"})[
        ["target_week_start", "week_end", "weekly_mean_observed_days", "eligible", "partial_week"]]
    for f in (hist, era5, fire, mbf):
        t = t.merge(f, on="target_week_start", how="left")
    thu = t["target_week_start"] + pd.Timedelta(days=3)
    t["smog_season_week"] = thu.dt.month.isin(SMOG_MONTHS)
    groups = {
        "history": list(hm.FEATURES),
        "era5": [c for c in era5.columns if c.startswith("era5_prev_")],
        "fire": [c for c in fire.columns if c.startswith("fire_prev_")],
        "massbalance": [c for c in mbf.columns if c.startswith("mb_prev_")],
    }
    layers = {
        "L1_history": groups["history"],
        "L2_plus_era5": groups["history"] + groups["era5"],
        "L3_plus_fire": groups["history"] + groups["era5"] + groups["fire"],
        "L4_plus_massbalance": groups["history"] + groups["era5"] + groups["fire"] + groups["massbalance"],
    }
    return t.sort_values("target_week_start", ignore_index=True), layers


def walk_forward_rf(table: pd.DataFrame, features: list[str], targets, params: dict = RF_PARAMS,
                    min_train: int = MIN_TRAIN_ROWS) -> pd.DataFrame:
    """Refit a Random Forest for each target week on strictly earlier eligible weeks."""
    usable = table[features].notna().all(axis=1)
    out = []
    for tgt in sorted({bl.issuance_cutoff(x) for x in targets}):
        row = {"target_week_start": tgt, "pred": np.nan, "n_train": 0, "reason": "ok"}
        f = table.loc[table["target_week_start"].eq(tgt)]
        if f.empty or not usable.loc[f.index].iloc[0]:
            row["reason"] = "missing_features"
            out.append(row)
            continue
        train = table[(table["week_end"] < tgt) & table["eligible"] & usable]
        row["n_train"] = len(train)
        if len(train) < min_train:
            row["reason"] = "too_little_training_data"
            out.append(row)
            continue
        model = RandomForestRegressor(**params)
        model.fit(train[features].to_numpy(float), train["weekly_mean_observed_days"].to_numpy(float))
        row["pred"] = float(model.predict(f[features].to_numpy(float))[0])
        out.append(row)
    return pd.DataFrame(out)


def mae(e: np.ndarray) -> float:
    return float(np.mean(np.abs(e)))


def block_bootstrap_mae_diff(err_a: np.ndarray, err_b: np.ndarray, block: int = BLOCK_WEEKS,
                             n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Paired moving-block bootstrap of MAE(a) − MAE(b) over consecutive weeks (time order kept)."""
    d = np.abs(err_a) - np.abs(err_b)
    n = len(d)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, max(n - block + 1, 1), size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    boot = d[idx].mean(axis=1)
    return {"mae_diff": float(d.mean()), "ci95_low": float(np.quantile(boot, 0.025)),
            "ci95_high": float(np.quantile(boot, 0.975)), "share_boot_below_0": float(np.mean(boot < 0))}


def score_all(preds: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    rows = []
    e = preds[preds["observed_eligible"].eq(True)]
    common = e[methods].notna().all(axis=1)
    for subset, mask in [("all", common), ("smog", common & e["smog_season_week"]),
                         ("non_smog", common & ~e["smog_season_week"])]:
        obs = e.loc[mask, "observed"].to_numpy(float)
        for m in methods:
            err = e.loc[mask, m].to_numpy(float) - obs
            if len(err) == 0:
                rows.append({"subset": subset, "method": m, "n": 0, "mae": np.nan, "rmse": np.nan,
                             "bias": np.nan, "median_ae": np.nan})
                continue
            rows.append({"subset": subset, "method": m, "n": int(mask.sum()), "mae": mae(err),
                         "rmse": float(np.sqrt(np.mean(err ** 2))), "bias": float(err.mean()),
                         "median_ae": float(np.median(np.abs(err)))})
    return pd.DataFrame(rows).set_index(["subset", "method"]).round(2)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    table, layers = load_feature_table()
    base = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage2" / "all_baseline_predictions.csv",
                       parse_dates=["target_week_start"])
    targets = table.loc[~table["partial_week"], "target_week_start"]

    preds = base[["target_week_start", "observed", "observed_eligible", "smog_season_week",
                  "persistence", "climatology", "history_model"]].copy()
    reasons = {}
    for name, feats in layers.items():
        p = walk_forward_rf(table, feats, targets)
        reasons[name] = p["reason"].value_counts().to_dict()
        preds = preds.merge(p[["target_week_start", "pred"]].rename(columns={"pred": f"rf_{name}"}),
                            on="target_week_start", how="left")
        print(f"{name}: {len(feats)} features, {reasons[name]}", flush=True)
    # 6 dp: removes ~1e-13 run-to-run float noise from parallel tree prediction (n_jobs=-1)
    preds.to_csv(OUT_DIR / "predictions.csv", index=False, float_format="%.6f")

    methods = ["persistence", "climatology", "history_model"] + [f"rf_{n}" for n in layers]
    scores = score_all(preds, methods)
    scores.to_csv(OUT_DIR / "scores_common_set.csv")

    e = preds[preds["observed_eligible"].eq(True)]
    common = e[methods].notna().all(axis=1)
    c = e.loc[common].sort_values("target_week_start")
    obs = c["observed"].to_numpy(float)
    err = {m: c[m].to_numpy(float) - obs for m in methods}
    comparisons = [("rf_L1_history", "history_model"), ("rf_L2_plus_era5", "rf_L1_history"),
                   ("rf_L3_plus_fire", "rf_L2_plus_era5"), ("rf_L4_plus_massbalance", "rf_L3_plus_fire"),
                   ("rf_L4_plus_massbalance", "history_model"), ("rf_L4_plus_massbalance", "climatology"),
                   ("rf_L4_plus_massbalance", "persistence")]
    boot = []
    for a, b in comparisons:
        for subset, mask in [("all", np.ones(len(c), bool)), ("smog", c["smog_season_week"].to_numpy())]:
            r = block_bootstrap_mae_diff(err[a][mask], err[b][mask])
            boot.append({"model": a, "compared_to": b, "subset": subset, "n": int(mask.sum()), **r})
    boot = pd.DataFrame(boot).round(3)
    boot.to_csv(OUT_DIR / "mae_difference_bootstrap.csv", index=False)

    summary = {"rf_params": RF_PARAMS, "min_train_rows": MIN_TRAIN_ROWS, "layers": {k: len(v) for k, v in layers.items()},
               "prediction_reasons": reasons, "common_set_weeks": int(common.sum()),
               "common_set_smog_weeks": int((common & e["smog_season_week"]).sum()),
               "bootstrap": {"block_weeks": BLOCK_WEEKS, "n_boot": N_BOOT, "seed": SEED}}
    (OUT_DIR / "stage3_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print("\n=== SCORES (µg/m³; error = prediction − observed)\n", scores.to_string())
    print("\n=== MAE DIFFERENCE (model − compared_to; negative = model better), block bootstrap 95% CI\n", boot.to_string())


if __name__ == "__main__":
    main()
