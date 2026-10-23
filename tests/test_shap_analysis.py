"""Unit tests for src.shap_analysis (synthetic data only)."""

import numpy as np
import pandas as pd
import pytest

from src import shap_analysis as sa
from src import stage4_trajectory_model as s4
from tests.test_trajectory_features import _table_and_traj

FAST = {"n_estimators": 30, "min_samples_leaf": 2, "max_features": 1.0, "random_state": 0, "n_jobs": 1}


def test_feature_groups_cover_every_feature_once_and_reject_unknown():
    feats = ["log_last", "sin1", "era5_prev_t2m_mean_c", "fire_prev_r0_100_count", "mb_prev_vc_mean",
             "traj_frac_c1", "traj_frac_c6", "traj_mean_height_m"]
    g = sa.feature_groups(feats)
    assert g == {"log_last": "PM2.5 history", "sin1": "Calendar (season)", "era5_prev_t2m_mean_c": "ERA5 weather",
                 "fire_prev_r0_100_count": "Fire (FIRMS)", "mb_prev_vc_mean": "Mass balance",
                 "traj_frac_c1": "Trajectories", "traj_frac_c6": "Trajectories", "traj_mean_height_m": "Trajectories"}
    with pytest.raises(ValueError):
        sa.feature_groups(["mystery_feature"])


def test_group_summary_sums_within_group_before_abs():
    sv = pd.DataFrame({"a1": [2.0, -2.0], "a2": [-1.0, 1.0], "b": [3.0, 1.0]})
    groups = {"a1": "A", "a2": "A", "b": "B"}
    s = sa.group_summary(sv, groups, {"all": pd.Series([True, True])}).set_index("group")
    assert s.loc["A", "mean_abs_shap"] == pytest.approx(1.0)        # |2-1|, |-2+1| -> mean 1
    assert s.loc["B", "mean_abs_shap"] == pytest.approx(2.0)
    assert s.loc["A", "share_pct"] == pytest.approx(100 / 3)
    assert s.loc["A", "mean_signed_shap"] == pytest.approx(0.0)


def test_top_features_excludes_cluster_shares():
    sv = pd.DataFrame({"traj_frac_c1": [9.0], "log_last": [1.0], "era5_prev_x": [-2.0]})
    t = sa.top_features(sv, list(sv.columns), exclude=["traj_frac_c1"], n=5)
    assert t["feature"].tolist() == ["era5_prev_x", "log_last"]


def test_fold_shap_reproduces_walk_forward_and_is_additive():
    table, traj = _table_and_traj()
    tgt = table["target_week_start"].iloc[[95, 100]]
    sv = sa.fold_shap(table, ["noise"], tgt, traj, k=2, params=FAST, min_train=52)
    wf = s4.walk_forward_traj(table, ["noise"], tgt, traj, k=2, params=FAST, min_train=52)
    assert len(sv) == 2
    assert np.allclose(sv["prediction"].to_numpy(), wf["pred"].to_numpy())
    feats = [c for c in sv.columns if c not in ("target_week_start", "base_value", "prediction", "n_train")]
    assert np.allclose(sv["base_value"] + sv[feats].sum(axis=1), sv["prediction"], atol=1e-8)
