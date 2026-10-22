"""Stage 4: model layer 5 (HYSPLIT trajectory features), walk-forward with in-fold clustering.

Design pre-declared in results/tables/stage4_predeclaration.md (committed 2a4b644 before fitting).
Everything not listed there is unchanged from Stage 3 (src.main_model).

Usage (after src.main_model and src.followup_models):
    python -m src.stage4_trajectory_model
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from src import baselines as bl
from src import main_model as mm
from src import trajectory_features as tf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage4"


def walk_forward_traj(table: pd.DataFrame, base_features: list[str], targets, traj: pd.DataFrame,
                      k: int = tf.N_CLUSTERS, params: dict = mm.RF_PARAMS,
                      min_train: int = mm.MIN_TRAIN_ROWS) -> pd.DataFrame:
    """For each target week T: fit k-means on trajectories before T−7 d, build cluster shares for all
    weeks up to T with that fold's centres, add continuous trajectory features, then fit the RF on
    eligible weeks that ended before T and predict T."""
    cont = tf.weekly_continuous(traj)
    frac_cols = [f"traj_frac_c{i + 1}" for i in range(k)]
    feats = base_features + frac_cols + tf.CONT_FEATURES
    base = table.set_index("target_week_start")
    out = []
    for tgt in sorted({bl.issuance_cutoff(x) for x in targets}):
        rec = {"target_week_start": tgt, "pred": np.nan, "n_train": 0, "reason": "ok"}
        km = tf.fit_fold_clusters(traj, tgt, k=k)
        if km is None:
            rec["reason"] = "too_few_trajectories_for_clustering"
            out.append(rec)
            continue
        fr = tf.fold_cluster_fractions(traj, km, tgt, k=k)
        t = base.loc[:tgt].join(fr, how="left").join(cont[tf.CONT_FEATURES], how="left")
        usable = t[feats].notna().all(axis=1)
        if tgt not in t.index or not usable.get(tgt, False):
            rec["reason"] = "missing_features"
            out.append(rec)
            continue
        train = t[(t["week_end"] < tgt) & t["eligible"] & usable]
        rec["n_train"] = len(train)
        if len(train) < min_train:
            rec["reason"] = "too_little_training_data"
            out.append(rec)
            continue
        model = RandomForestRegressor(**params)
        model.fit(train[feats].to_numpy(float), train["weekly_mean_observed_days"].to_numpy(float))
        rec["pred"] = float(model.predict(t.loc[[tgt], feats].to_numpy(float))[0])
        out.append(rec)
    return pd.DataFrame(out)


def extended_scores(preds: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """MAE/RMSE/bias/median AE (src.main_model.score_all) plus R² and MAE skill vs persistence."""
    s = mm.score_all(preds, methods).reset_index()
    e = preds[preds["observed_eligible"].eq(True)]
    common = e[methods].notna().all(axis=1)
    rows = []
    for subset, mask in (("all", common), ("smog", common & e["smog_season_week"]),
                         ("non_smog", common & ~e["smog_season_week"])):
        obs = e.loc[mask, "observed"].to_numpy(float)
        sst = float(((obs - obs.mean()) ** 2).sum()) if len(obs) else np.nan
        mae_p = float(np.abs(e.loc[mask, "persistence"].to_numpy(float) - obs).mean()) if len(obs) else np.nan
        for m in methods:
            err = e.loc[mask, m].to_numpy(float) - obs
            rows.append({"subset": subset, "method": m,
                         "r2": 1 - float((err ** 2).sum()) / sst if len(obs) and sst > 0 else np.nan,
                         "skill_vs_persistence": 1 - float(np.abs(err).mean()) / mae_p if len(obs) else np.nan})
    return s.merge(pd.DataFrame(rows), on=["subset", "method"]).set_index(["subset", "method"]).round(3)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    traj = tf.per_trajectory(tf.load_endpoints())
    table, layers = mm.load_feature_table()
    targets = table.loc[~table["partial_week"], "target_week_start"]
    prev = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage3b" / "predictions_all_models.csv",
                       parse_dates=["target_week_start"])

    runs = {
        "rf_L5_plus_traj": (layers["L4_plus_massbalance"], tf.N_CLUSTERS),
        "rf_L1_plus_traj": (layers["L1_history"], tf.N_CLUSTERS),
        "rf_L5_plus_traj_k4": (layers["L4_plus_massbalance"], 4),
        "rf_L5_plus_traj_k8": (layers["L4_plus_massbalance"], 8),
    }
    preds = prev.copy()
    reasons = {}
    for name, (base_feats, k) in runs.items():
        p = walk_forward_traj(table, base_feats, targets, traj, k=k)
        reasons[name] = p["reason"].value_counts().to_dict()
        preds = preds.merge(p[["target_week_start", "pred"]].rename(columns={"pred": name}),
                            on="target_week_start", how="left")
        print(f"{name}: {reasons[name]}", flush=True)
    preds.to_csv(OUT_DIR / "predictions_all_models.csv", index=False, float_format="%.6f")

    methods = ["persistence", "climatology", "history_model", "rf_L1_history", "rf_L4_plus_massbalance",
               "rf_L5_plus_traj", "rf_L1_plus_traj", "rf_L5_plus_traj_k4", "rf_L5_plus_traj_k8"]
    scores = extended_scores(preds, methods)
    scores.to_csv(OUT_DIR / "scores_common_set.csv")

    e = preds[preds["observed_eligible"].eq(True)]
    common = e[methods].notna().all(axis=1)
    c = e.loc[common].sort_values("target_week_start")
    obs = c["observed"].to_numpy(float)
    err = {m: c[m].to_numpy(float) - obs for m in methods}
    smog = c["smog_season_week"].to_numpy()
    comps = [("rf_L5_plus_traj", "rf_L4_plus_massbalance", (4, 2, 8)),
             ("rf_L1_plus_traj", "rf_L1_history", (4,)),
             ("rf_L5_plus_traj", "history_model", (4,)),
             ("rf_L5_plus_traj", "climatology", (4,)),
             ("rf_L5_plus_traj", "persistence", (4,))]
    boot = []
    for a, b, blocks in comps:
        for blk in blocks:
            for subset, mask in (("all", np.ones(len(c), bool)), ("smog", smog)):
                boot.append({"model": a, "compared_to": b, "block_weeks": blk, "subset": subset, "n": int(mask.sum()),
                             **mm.block_bootstrap_mae_diff(err[a][mask], err[b][mask], block=blk)})
    boot = pd.DataFrame(boot).round(3)
    boot.to_csv(OUT_DIR / "mae_difference_bootstrap.csv", index=False)

    summary = {"predeclaration": "results/tables/stage4_predeclaration.md", "trajectories": len(traj),
               "trajectory_days": [str(traj["date_pkt"].min().date()), str(traj["date_pkt"].max().date())],
               "k_primary": tf.N_CLUSTERS, "prediction_reasons": reasons,
               "common_set_weeks": int(common.sum()), "common_set_smog_weeks": int((common & e["smog_season_week"]).sum()),
               "common_set_span": [str(c["target_week_start"].min().date()), str(c["target_week_start"].max().date())]}
    (OUT_DIR / "stage4_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print("\n=== SCORES\n", scores.to_string())
    print("\n=== MAE DIFFERENCES (negative = first model better)\n", boot.to_string())


if __name__ == "__main__":
    main()
