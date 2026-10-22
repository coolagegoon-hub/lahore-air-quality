"""PM2.5-history-only baseline model for weekly mean PM2.5, evaluated walk-forward.

Design (fixed before seeing any results; nothing below was tuned on the evaluation period):
- Target: log of the weekly mean PM2.5 of week T (eligible weeks only; src.weekly_targets with
  the project rule >= 6 of 7 valid days).
- Forecast issued at Monday 00:00 PKT of week T (src.baselines.issuance_cutoff). Features use
  only eligible weeks that ENDED before that cutoff, within the previous LOOKBACK_WEEKS weeks:
    log_last    log of the most recent eligible weekly mean
    age_last    weeks between that source week and T (1 = previous week)
    log_mean4   log of the mean of eligible weekly means in the lookback window
    n_recent    number of eligible weeks in the lookback window
    sin1, cos1, sin2, cos2   annual harmonics of the target week's Thursday (day of year),
                which are known in advance (calendar only)
  No feature is computed from week T itself. A target with no eligible week in the lookback
  window gets no prediction (reason recorded); nothing is imputed.
- Model: StandardScaler + Ridge(alpha=RIDGE_ALPHA) from scikit-learn, refitted from scratch for
  every target week on training rows whose target week ended before the cutoff (expanding
  window, strict chronological order). The scaler is fitted on training rows only.
- Back-transform: exp(prediction) × Duan smearing factor (mean of exp(training residuals)),
  computed from the same training rows only.
- Minimum training size MIN_TRAIN_ROWS; earlier targets get no prediction.
- No randomness (Ridge closed form), so no seed is needed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import baselines as bl

LOOKBACK_WEEKS = 4
RIDGE_ALPHA = 1.0
MIN_TRAIN_ROWS = 52
FEATURES = ["log_last", "age_last", "log_mean4", "n_recent", "sin1", "cos1", "sin2", "cos2"]


def features_for_targets(weekly: pd.DataFrame, target_week_starts) -> pd.DataFrame:
    """Feature rows for each target week, using only eligible weeks that ended before its cutoff."""
    w = bl._validate_weekly(weekly)
    elig = w[w["eligible"] & w["weekly_mean_observed_days"].notna()]
    starts = elig["week_start"].to_numpy()
    vals = elig["weekly_mean_observed_days"].to_numpy(dtype=float)
    rows = []
    for t in target_week_starts:
        cutoff = bl.issuance_cutoff(t)
        lo = cutoff - pd.Timedelta(weeks=LOOKBACK_WEEKS)
        # week_end < cutoff  <=>  week_start <= cutoff - 7 days
        m = (starts >= lo.to_datetime64()) & (starts <= (cutoff - pd.Timedelta(days=7)).to_datetime64())
        thu = cutoff + pd.Timedelta(days=3)
        ang = 2 * np.pi * thu.dayofyear / 365.25
        row = {"target_week_start": cutoff, "sin1": np.sin(ang), "cos1": np.cos(ang),
               "sin2": np.sin(2 * ang), "cos2": np.cos(2 * ang)}
        if m.any():
            last_i = np.flatnonzero(m)[-1]
            row.update(log_last=np.log(vals[last_i]),
                       age_last=float((cutoff - pd.Timestamp(starts[last_i])).days // 7),
                       log_mean4=np.log(vals[m].mean()), n_recent=float(m.sum()), reason="ok")
        else:
            row.update(log_last=np.nan, age_last=np.nan, log_mean4=np.nan, n_recent=0.0,
                       reason="no_eligible_week_in_lookback")
        rows.append(row)
    return pd.DataFrame(rows)


def walk_forward(weekly: pd.DataFrame, target_week_starts) -> pd.DataFrame:
    """Refit the model for every target week on strictly earlier data; return predictions."""
    w = bl._validate_weekly(weekly)
    all_starts = sorted(w["week_start"])
    feats = features_for_targets(w, all_starts).set_index("target_week_start")
    truth = w.set_index("week_start")
    feats["y"] = np.log(truth["weekly_mean_observed_days"].where(truth["eligible"]))
    feats["week_end"] = truth["week_end"]

    out = []
    for t in sorted({bl.issuance_cutoff(x) for x in target_week_starts}):
        row = {"target_week_start": t, "history_model": np.nan, "n_train": 0}
        f = feats.loc[t] if t in feats.index else None
        if f is None or f["reason"] != "ok":
            row["history_reason"] = "no_features" if f is None else f["reason"]
            out.append(row)
            continue
        train = feats[(feats["week_end"] < t) & feats["y"].notna() & (feats["reason"] == "ok")]
        row["n_train"] = len(train)
        if len(train) < MIN_TRAIN_ROWS:
            row["history_reason"] = "too_little_training_data"
            out.append(row)
            continue
        model = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
        X, y = train[FEATURES].to_numpy(dtype=float), train["y"].to_numpy(dtype=float)
        model.fit(X, y)
        smear = float(np.mean(np.exp(y - model.predict(X))))
        pred_log = float(model.predict(f[FEATURES].to_numpy(dtype=float)[None, :])[0])
        row.update(history_model=float(np.exp(pred_log) * smear), history_reason="ok")
        out.append(row)
    return pd.DataFrame(out)


def comparison_scores(preds: pd.DataFrame) -> pd.DataFrame:
    """MAE/RMSE/bias of all baselines on eligible observed weeks where ALL are available,
    overall and split by smog season (src.stage2_weekly.score; error = prediction − observed)."""
    from src.stage2_weekly import score

    cols = ["persistence", "climatology", "history_model"]
    e = preds[preds["observed_eligible"].eq(True)]
    common = e[cols].notna().all(axis=1)
    rows = []
    for subset, mask in [("all", common), ("smog", common & e["smog_season_week"]),
                         ("non_smog", common & ~e["smog_season_week"])]:
        for c in cols:
            rows.append({"subset": subset, "baseline": c, **score(e.loc[mask, "observed"], e.loc[mask, c])})
    return pd.DataFrame(rows).set_index(["subset", "baseline"]).round(2)


def main() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out_dir = root / "results" / "tables" / "stage2"
    weekly = pd.read_csv(root / "data" / "processed" / "pm25_weekly_target.csv", parse_dates=["week_start", "week_end"])
    base = pd.read_csv(out_dir / "baseline_predictions.csv", parse_dates=["target_week_start"])
    hist = walk_forward(weekly, base["target_week_start"])
    preds = base.merge(hist, on="target_week_start", how="left")
    preds.to_csv(out_dir / "all_baseline_predictions.csv", index=False)
    scores = comparison_scores(preds)
    scores.to_csv(out_dir / "all_baseline_scores_common_set.csv")
    summary = {"history_reasons": hist["history_reason"].value_counts().to_dict(),
               "lookback_weeks": LOOKBACK_WEEKS, "ridge_alpha": RIDGE_ALPHA, "min_train_rows": MIN_TRAIN_ROWS,
               "features": FEATURES}
    (out_dir / "history_model_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(scores.to_string())


if __name__ == "__main__":
    main()
