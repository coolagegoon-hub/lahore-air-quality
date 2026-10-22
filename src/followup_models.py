"""Stage 3b: pre-declared follow-up models (see results/tables/stage3b_predeclaration.md).

Model A "rflog": Random Forest on log(weekly mean PM2.5), Stage 3 settings + oob_score, back-
transformed with exp × Duan smearing from out-of-bag residuals of the same training fold.
Model B "ridgeall": StandardScaler + Ridge(alpha=1.0) on log(weekly mean PM2.5) with all features
of the layer; fire_prev_* features get a fixed log1p transform first; back-transformed with
exp × Duan smearing from the training residuals of the same fold.

Both are refitted for every target week on eligible weeks that ended before its cutoff
(expanding window, >= MIN_TRAIN_ROWS), on layers L1–L4 from src.main_model. Results are reported
alongside Stage 3; nothing here was tuned on the evaluation period.

Usage (after src.main_model):
    python -m src.followup_models
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import baselines as bl
from src import main_model as mm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage3b"
RFLOG_PARAMS = {**mm.RF_PARAMS, "oob_score": True}
RIDGE_ALPHA = 1.0


def log1p_fire(X: pd.DataFrame) -> pd.DataFrame:
    """Fixed (unfitted) transform: log1p of fire count/FRP features; others unchanged."""
    X = X.copy()
    fire = [c for c in X.columns if c.startswith("fire_prev_")]
    if fire:
        X[fire] = np.log1p(X[fire].clip(lower=0))
    return X


def _fit_predict(kind: str, train: pd.DataFrame, row: pd.DataFrame, features: list[str],
                 rf_params: dict) -> float:
    y = np.log(train["weekly_mean_observed_days"].to_numpy(float))
    if kind == "rflog":
        model = RandomForestRegressor(**rf_params)
        X = train[features].to_numpy(float)
        model.fit(X, y)
        oob = model.oob_prediction_
        smear = float(np.mean(np.exp(y - oob)))
        pred_log = float(model.predict(row[features].to_numpy(float))[0])
    elif kind == "ridgeall":
        Xtr = log1p_fire(train[features]).to_numpy(float)
        Xte = log1p_fire(row[features]).to_numpy(float)
        model = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
        model.fit(Xtr, y)
        smear = float(np.mean(np.exp(y - model.predict(Xtr))))
        pred_log = float(model.predict(Xte)[0])
    else:
        raise ValueError(kind)
    return float(np.exp(pred_log) * smear)


def walk_forward(table: pd.DataFrame, features: list[str], targets, kind: str,
                 rf_params: dict = RFLOG_PARAMS, min_train: int = mm.MIN_TRAIN_ROWS) -> pd.DataFrame:
    """Refit the chosen follow-up model for each target week on strictly earlier eligible weeks."""
    usable = table[features].notna().all(axis=1)
    out = []
    for tgt in sorted({bl.issuance_cutoff(x) for x in targets}):
        rec = {"target_week_start": tgt, "pred": np.nan, "n_train": 0, "reason": "ok"}
        row = table.loc[table["target_week_start"].eq(tgt)]
        if row.empty or not usable.loc[row.index].iloc[0]:
            rec["reason"] = "missing_features"
            out.append(rec)
            continue
        train = table[(table["week_end"] < tgt) & table["eligible"] & usable
                      & table["weekly_mean_observed_days"].gt(0)]
        rec["n_train"] = len(train)
        if len(train) < min_train:
            rec["reason"] = "too_little_training_data"
            out.append(rec)
            continue
        rec["pred"] = _fit_predict(kind, train, row, features, rf_params)
        out.append(rec)
    return pd.DataFrame(out)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    table, layers = mm.load_feature_table()
    stage3 = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage3" / "predictions.csv",
                         parse_dates=["target_week_start"])
    targets = table.loc[~table["partial_week"], "target_week_start"]

    preds = stage3.copy()
    reasons = {}
    for kind in ("rflog", "ridgeall"):
        for name, feats in layers.items():
            p = walk_forward(table, feats, targets, kind)
            col = f"{kind}_{name}"
            reasons[col] = p["reason"].value_counts().to_dict()
            preds = preds.merge(p[["target_week_start", "pred"]].rename(columns={"pred": col}),
                                on="target_week_start", how="left")
            print(f"{col}: {reasons[col]}", flush=True)
    # 6 dp: removes ~1e-13 run-to-run float noise from parallel tree prediction (n_jobs=-1)
    preds.to_csv(OUT_DIR / "predictions_all_models.csv", index=False, float_format="%.6f")

    rf_cols = [f"rf_{n}" for n in layers]
    new_cols = [f"{k}_{n}" for k in ("rflog", "ridgeall") for n in layers]
    methods = ["persistence", "climatology", "history_model"] + rf_cols + new_cols
    scores = mm.score_all(preds, methods)
    scores.to_csv(OUT_DIR / "scores_common_set.csv")

    e = preds[preds["observed_eligible"].eq(True)]
    common = e[methods].notna().all(axis=1)
    c = e.loc[common].sort_values("target_week_start")
    obs = c["observed"].to_numpy(float)
    err = {m: c[m].to_numpy(float) - obs for m in methods}
    L = list(layers)
    comps = [("rflog_L4_plus_massbalance", "rf_L4_plus_massbalance"),
             ("ridgeall_L4_plus_massbalance", "history_model"),
             ("rflog_L4_plus_massbalance", "history_model"),
             ("rflog_L4_plus_massbalance", "climatology"), ("rflog_L4_plus_massbalance", "persistence"),
             ("ridgeall_L4_plus_massbalance", "climatology"), ("ridgeall_L4_plus_massbalance", "persistence")]
    for fam in ("rflog", "ridgeall"):
        comps += [(f"{fam}_{L[i]}", f"{fam}_{L[i - 1]}") for i in range(1, len(L))]
    boot = []
    smog = c["smog_season_week"].to_numpy()
    for a, b in comps:
        for subset, mask in (("all", np.ones(len(c), bool)), ("smog", smog)):
            boot.append({"model": a, "compared_to": b, "subset": subset, "n": int(mask.sum()),
                         **mm.block_bootstrap_mae_diff(err[a][mask], err[b][mask])})
    boot = pd.DataFrame(boot).round(3)
    boot.to_csv(OUT_DIR / "mae_difference_bootstrap.csv", index=False)

    summary = {"predeclaration": "results/tables/stage3b_predeclaration.md", "rflog_params": RFLOG_PARAMS,
               "ridge_alpha": RIDGE_ALPHA, "prediction_reasons": reasons,
               "common_set_weeks": int(common.sum()), "common_set_smog_weeks": int((common & e["smog_season_week"]).sum())}
    (OUT_DIR / "stage3b_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: v for k, v in summary.items() if k != "prediction_reasons"}, indent=2, default=str))
    print("\n=== SCORES (µg/m³)\n", scores.to_string())
    print("\n=== MAE DIFFERENCES (negative = first model better), 95% block-bootstrap CI\n", boot.to_string())


if __name__ == "__main__":
    main()
