"""Stage 5: fold-by-fold SHAP analysis of the layer-5 Random Forest (rf_L5_plus_traj, k = 6).

Design pre-declared in results/tables/stage5_shap_predeclaration.md (committed before computing).
SHAP describes what the model relied on for each out-of-sample forecast. It is NOT causal source
attribution (CLAUDE.md interpretation rules).

Usage (after src.stage4_trajectory_model):
    python -m src.shap_analysis
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402

from src import baselines as bl  # noqa: E402
from src import main_model as mm  # noqa: E402
from src import trajectory_features as tf  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage5"
FIG_DIR = PROJECT_ROOT / "results" / "figures"
HISTORY = ["log_last", "age_last", "log_mean4", "n_recent"]
CALENDAR = ["sin1", "cos1", "sin2", "cos2"]
TOL = 1e-6


def feature_groups(features: list[str], k: int = tf.N_CLUSTERS) -> dict[str, str]:
    """Map every feature to exactly one group (raises if any feature is unmapped)."""
    traj = [f"traj_frac_c{i + 1}" for i in range(k)] + list(tf.CONT_FEATURES)
    groups = {}
    for f in features:
        if f in HISTORY:
            groups[f] = "PM2.5 history"
        elif f in CALENDAR:
            groups[f] = "Calendar (season)"
        elif f.startswith("era5_prev_"):
            groups[f] = "ERA5 weather"
        elif f.startswith("fire_prev_"):
            groups[f] = "Fire (FIRMS)"
        elif f.startswith("mb_prev_"):
            groups[f] = "Mass balance"
        elif f in traj:
            groups[f] = "Trajectories"
        else:
            raise ValueError(f"feature {f!r} has no group")
    return groups


def fold_shap(table: pd.DataFrame, base_features: list[str], targets, traj: pd.DataFrame,
              k: int = tf.N_CLUSTERS, params: dict = mm.RF_PARAMS, min_train: int = mm.MIN_TRAIN_ROWS) -> pd.DataFrame:
    """Refit each fold exactly as src.stage4_trajectory_model.walk_forward_traj and return one row per
    forecast with base value, prediction and the SHAP value of every feature (test row only)."""
    cont = tf.weekly_continuous(traj)
    frac_cols = [f"traj_frac_c{i + 1}" for i in range(k)]
    feats = base_features + frac_cols + tf.CONT_FEATURES
    base = table.set_index("target_week_start")
    rows = []
    for tgt in sorted({bl.issuance_cutoff(x) for x in targets}):
        km = tf.fit_fold_clusters(traj, tgt, k=k)
        if km is None:
            continue
        fr = tf.fold_cluster_fractions(traj, km, tgt, k=k)
        t = base.loc[:tgt].join(fr, how="left").join(cont[tf.CONT_FEATURES], how="left")
        usable = t[feats].notna().all(axis=1)
        if tgt not in t.index or not usable.get(tgt, False):
            continue
        train = t[(t["week_end"] < tgt) & t["eligible"] & usable]
        if len(train) < min_train:
            continue
        model = RandomForestRegressor(**params)
        model.fit(train[feats].to_numpy(float), train["weekly_mean_observed_days"].to_numpy(float))
        x = t.loc[[tgt], feats].to_numpy(float)
        explainer = shap.TreeExplainer(model)
        sv = np.asarray(explainer.shap_values(x))[0]
        ev = float(np.ravel(explainer.expected_value)[0])
        rows.append({"target_week_start": tgt, "base_value": ev, "prediction": float(model.predict(x)[0]),
                     "n_train": len(train), **dict(zip(feats, sv))})
    return pd.DataFrame(rows)


def group_summary(sv: pd.DataFrame, groups: dict[str, str], subsets: dict[str, pd.Series]) -> pd.DataFrame:
    """Per subset and group: mean |group SHAP|, its share of the total, and mean signed group SHAP."""
    g = pd.DataFrame({name: sv[[f for f, gr in groups.items() if gr == name]].sum(axis=1)
                      for name in dict.fromkeys(groups.values())})
    rows = []
    for subset, mask in subsets.items():
        sub = g[mask.to_numpy()]
        mabs = sub.abs().mean()
        for name in g.columns:
            rows.append({"subset": subset, "group": name, "n_weeks": int(len(sub)),
                         "mean_abs_shap": float(mabs[name]), "share_pct": float(100 * mabs[name] / mabs.sum()),
                         "mean_signed_shap": float(sub[name].mean())})
    return pd.DataFrame(rows)


def top_features(sv: pd.DataFrame, features: list[str], exclude: list[str], n: int = 10) -> pd.DataFrame:
    keep = [f for f in features if f not in exclude]
    m = sv[keep].abs().mean().sort_values(ascending=False).head(n)
    return pd.DataFrame({"feature": m.index, "mean_abs_shap": m.to_numpy()})


def plot_groups(summary: pd.DataFrame, path_stem: Path) -> list[Path]:
    from src import figures_data as fd

    fd.style()
    order = summary[summary["subset"] == "all"].sort_values("mean_abs_shap")["group"].tolist()
    a = summary[summary["subset"] == "all"].set_index("group").loc[order]
    s = summary[summary["subset"] == "smog"].set_index("group").loc[order]
    y = np.arange(len(order))
    h = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.barh(y + h / 2 + 0.01, a["mean_abs_shap"], h, color=fd.BLUE, label=f"All forecast weeks (n = {int(a['n_weeks'].iloc[0])})")
    ax.barh(y - h / 2 - 0.01, s["mean_abs_shap"], h, color=fd.ORANGE, label=f"Oct–Jan weeks (n = {int(s['n_weeks'].iloc[0])})")
    for yi, v in zip(y, a["mean_abs_shap"]):
        ax.text(v + 0.3, yi + h / 2, f"{v:.1f}", va="center", fontsize=8.5, color=fd.INK_2)
    for yi, v in zip(y, s["mean_abs_shap"]):
        ax.text(v + 0.3, yi - h / 2, f"{v:.1f}", va="center", fontsize=8.5, color=fd.INK_2)
    ax.set_yticks(y, order)
    ax.set_xlabel("Mean |group SHAP value| (µg/m³)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title("What the layer-5 Random Forest relied on, by input group", loc="left")
    ax.text(0.0, -0.2, "Out-of-sample SHAP: one explanation per walk-forward forecast, from that week's own model. "
            "Model reliance, not causal attribution.\nPM2.5: U.S. Consulate Lahore via EPA AirNow (U.S. Department of State); "
            "preliminary data.", transform=ax.transAxes, fontsize=8, color=fd.INK_2, va="top")
    paths = []
    for ext in ("png", "pdf"):
        p = path_stem.with_suffix(f".{ext}")
        fig.savefig(p, dpi=300, bbox_inches="tight", metadata=fd.NO_DATE.get(ext))
        paths.append(p)
    plt.close(fig)
    return paths


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    traj = tf.per_trajectory(tf.load_endpoints())
    table, layers = mm.load_feature_table()
    targets = table.loc[~table["partial_week"], "target_week_start"]
    base_feats = layers["L4_plus_massbalance"]
    sv = fold_shap(table, base_feats, targets, traj)
    feats = [c for c in sv.columns if c not in ("target_week_start", "base_value", "prediction", "n_train")]
    groups = feature_groups(feats)

    # reproduction and additivity checks
    s4 = pd.read_csv(PROJECT_ROOT / "results" / "tables" / "stage4" / "predictions_all_models.csv",
                     parse_dates=["target_week_start"])
    m = sv.merge(s4[["target_week_start", "rf_L5_plus_traj", "observed", "observed_eligible", "smog_season_week",
                     "persistence", "climatology", "history_model", "rf_L1_history", "rf_L4_plus_massbalance",
                     "rf_L1_plus_traj", "rf_L5_plus_traj_k4", "rf_L5_plus_traj_k8"]], on="target_week_start", how="left")
    repro_err = float((m["prediction"] - m["rf_L5_plus_traj"]).abs().max())
    add_err = float((sv["base_value"] + sv[feats].sum(axis=1) - sv["prediction"]).abs().max())
    if repro_err > TOL or add_err > TOL:
        raise SystemExit(f"check failed: reproduction error {repro_err}, additivity error {add_err}")

    methods = ["persistence", "climatology", "history_model", "rf_L1_history", "rf_L4_plus_massbalance",
               "rf_L5_plus_traj", "rf_L1_plus_traj", "rf_L5_plus_traj_k4", "rf_L5_plus_traj_k8"]
    common = m["observed_eligible"].eq(True) & m[methods].notna().all(axis=1)
    smog = m["smog_season_week"].eq(True)
    subsets = {"all": common, "smog": common & smog, "non_smog": common & ~smog}
    summary = group_summary(m[feats], groups, subsets)
    clusters = [f"traj_frac_c{i + 1}" for i in range(tf.N_CLUSTERS)]
    top_all = top_features(m.loc[common, feats], feats, clusters).assign(group=lambda d: d["feature"].map(groups))
    top_smog = top_features(m.loc[common & smog, feats], feats, clusters).assign(group=lambda d: d["feature"].map(groups))

    sv.to_csv(OUT_DIR / "shap_values_per_forecast.csv", index=False, float_format="%.6f")
    summary.round(3).to_csv(OUT_DIR / "shap_group_summary.csv", index=False)
    top_all.round(3).to_csv(OUT_DIR / "shap_top_features_all.csv", index=False)
    top_smog.round(3).to_csv(OUT_DIR / "shap_top_features_smog.csv", index=False)
    figs = plot_groups(summary, FIG_DIR / "fig5_shap_groups")

    info = {"predeclaration": "results/tables/stage5_shap_predeclaration.md", "shap_version": shap.__version__,
            "forecasts_explained": len(sv), "max_reproduction_error": repro_err, "max_additivity_error": add_err,
            "weeks": {k: int(v.sum()) for k, v in subsets.items()}, "figures": [str(p.relative_to(PROJECT_ROOT)) for p in figs]}
    (OUT_DIR / "stage5_summary.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))
    print("\n=== GROUP SUMMARY\n", summary.round(2).to_string(index=False))
    print("\n=== TOP FEATURES (all)\n", top_all.round(2).to_string(index=False))
    print("\n=== TOP FEATURES (Oct–Jan)\n", top_smog.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
