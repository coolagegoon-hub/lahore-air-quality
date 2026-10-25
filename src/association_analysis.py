"""Stage 7: air-mass pathway association analysis (H1-H3), as pre-declared in
results/tables/stage7_association_predeclaration.md (commit 57f17be, before any result).

Association only: no forecasting, no source attribution, no causal claims.

Unit: a PKT day with a complete daily PM2.5 mean (>= 18/24 valid hours, after the 7-hour
repeated-value rule) and a HYSPLIT trajectory arriving that day (06:00 UTC = 11:00 PKT).
Outcome: log daily mean PM2.5. Seasons: DJF winter, MAM pre-monsoon, JJAS monsoon, ON
post-monsoon (primary); October-January (secondary).

Steps
1. Descriptive Ward clustering of all 2,161 trajectories (24-number km shape vector, as in
   src.trajectory_features). k = largest k in 2..10 with Delta(k) >= 30%, where
   Delta(k) = 100 * [TSV(k-1) - TSV(k)] / TSV(k); if none, the k with the largest Delta(k).
2. Pathway variables: cluster, 72-h transport distance, within-season distance tercile,
   east/south-east endpoint share, mean endpoint height.
3. Daily ERA5 weather at 31.50 N 74.25 E (PKT days, same conversions as src.era5_features).
4. Trajectory-weighted fire exposure: unique VIIRS Suomi NPP detections (vegetation, nominal or
   high confidence) within 50 km of an hourly endpoint (hours 1-72, height <= 1,500 m AGL) whose
   PKT detection date is the endpoint's PKT date or the day before; FE = their total FRP (MW).
5. Tests: moving-block bootstrap (7-day blocks within season-year, 2,000 resamples, seed
   20261025) for intervals; block permutation (7-day blocks within season-year, 2,000) for p.
6. CWT maps on a 1-degree grid with openair-style low-count weights.

Usage:
    python -m src.association_analysis
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

from src import era5_features as ef
from src import firms_features as ff
from src import trajectory_features as tf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROC = PROJECT_ROOT / "data" / "processed"
OUT_DIR = PROJECT_ROOT / "results" / "tables" / "stage7"
TZ = "Asia/Karachi"

K_RANGE = range(2, 11)
TSV_JUMP_PCT = 30.0
SEED_KMEANS = 20261021
SEED = 20261025
N_BOOT = 2000
N_PERM = 2000
BLOCK_DAYS = 7
BLOCK_CHECKS = (14, 28)
MIN_CELL_DAYS = 30
FIRE_BUFFER_KM = 50.0
FIRE_BUFFERS_SENS = (25.0, 100.0)
FIRE_MAX_HEIGHT_M = 1500.0
NULL_SHIFTS = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)
MISSING_SAT_NOAA20_MIN = 100
CLIM_HALF_WINDOW = 15
CWT_GRID_DEG = 1.0
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "pre-monsoon", 4: "pre-monsoon", 5: "pre-monsoon",
           6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon", 10: "post-monsoon", 11: "post-monsoon"}
SEASON_ORDER = ["winter", "pre-monsoon", "monsoon", "post-monsoon"]


# ------------------------------------------------------------------ data assembly

def season_of(dates: pd.DatetimeIndex) -> np.ndarray:
    return np.array([SEASONS[m] for m in dates.month])


def season_year(dates: pd.DatetimeIndex) -> np.ndarray:
    """Year label of each day's season; December belongs to the following year's winter."""
    return np.where(dates.month == 12, dates.year + 1, dates.year)


def load_days() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Analysis days (complete PM2.5 and a trajectory), all trajectories, and the endpoints."""
    pm = pd.read_csv(PROC / "pm25_daily_final.csv", parse_dates=["date"])
    pm = pm[pm["complete"].eq(True) & pm["pm25_daily_mean"].gt(0)]
    ends = tf.load_endpoints()
    traj = tf.per_trajectory(ends)
    if traj["date_pkt"].duplicated().any():
        raise ValueError("more than one trajectory on a PKT day")
    days = pm[["date", "pm25_daily_mean"]].merge(traj.reset_index(), left_on="date", right_on="date_pkt", how="inner")
    days = days.drop(columns="date_pkt").sort_values("date").reset_index(drop=True)
    idx = pd.DatetimeIndex(days["date"])
    days["log_pm"] = np.log(days["pm25_daily_mean"])
    days["season"] = season_of(idx)
    days["season_year"] = season_year(idx)
    days["oct_jan"] = idx.month.isin([10, 11, 12, 1])
    days["doy"] = idx.dayofyear
    days["year"] = idx.year
    return days, traj, ends


# ------------------------------------------------------------------ clustering

def tsv_curve(labels_by_k: dict[int, np.ndarray], X: np.ndarray) -> pd.Series:
    """Total within-cluster sum of squared distances for each k."""
    out = {}
    for k, lab in labels_by_k.items():
        out[k] = float(sum(((X[lab == c] - X[lab == c].mean(axis=0)) ** 2).sum() for c in np.unique(lab)))
    return pd.Series(out).sort_index()


def choose_k(tsv: pd.Series, jump_pct: float = TSV_JUMP_PCT) -> tuple[int, pd.Series]:
    """Delta(k) = % increase in TSV when going from k to k-1 clusters; pick the largest k with
    Delta(k) >= jump_pct, otherwise the k with the largest Delta(k)."""
    delta = pd.Series({k: 100 * (tsv[k - 1] - tsv[k]) / tsv[k] for k in tsv.index if k - 1 in tsv.index})
    hits = delta[delta >= jump_pct]
    k = int(hits.index.max()) if len(hits) else int(delta.idxmax())
    return k, delta


def ward_clusters(traj: pd.DataFrame) -> dict:
    X = traj[tf.shape_columns()].to_numpy(float)
    Z = linkage(X, method="ward")
    labels = {k: fcluster(Z, k, criterion="maxclust") for k in list(K_RANGE) + [1]}
    tsv = tsv_curve(labels, X)
    k, delta = choose_k(tsv)
    sil = {kk: float(silhouette_score(X, labels[kk])) for kk in K_RANGE}
    km = KMeans(n_clusters=k, n_init=20, random_state=SEED_KMEANS).fit(X)
    ari = float(adjusted_rand_score(labels[k], km.labels_))
    return {"X": X, "labels": labels, "tsv": tsv, "delta": delta, "k": k, "silhouette": sil, "kmeans_ari": ari}


COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def relabel_and_name(traj: pd.DataFrame, raw_labels: np.ndarray) -> tuple[np.ndarray, pd.DataFrame]:
    """Number clusters 1..k by mean 72-h distance (1 = slowest) and describe each by speed and
    the direction its air came from (bearing of the mean 72-h position)."""
    t = traj.assign(raw=raw_labels)
    summ = t.groupby("raw").agg(n=("raw", "size"), dist72=("traj_mean_dist72_km", "mean"),
                                x72=("x72", "mean"), y72=("y72", "mean"), height=("traj_mean_height_m", "mean"))
    summ = summ.sort_values("dist72")
    summ["cluster"] = np.arange(1, len(summ) + 1)
    bearing = (np.degrees(np.arctan2(summ["x72"], summ["y72"])) + 360) % 360
    summ["from_dir"] = [COMPASS[int(((b + 22.5) % 360) // 45)] for b in bearing]
    summ["speed"] = pd.cut(summ["dist72"], [0, 400, 900, np.inf], labels=["slow", "moderate", "fast"]).astype(str)
    summ["name"] = [f"C{c}: {s}, from {d}" for c, s, d in zip(summ["cluster"], summ["speed"], summ["from_dir"])]
    summ["share_pct"] = 100 * summ["n"] / summ["n"].sum()
    mapping = summ["cluster"].to_dict()
    return np.array([mapping[r] for r in raw_labels]), summ.reset_index(drop=True)


# ------------------------------------------------------------------ weather

def daily_weather() -> pd.DataFrame:
    h = ef.to_hourly_pkt(ef.load_raw())
    h["vc"] = h["blh_m"] * h["ws10"]
    gi = h.groupby("day_instant")
    d = pd.DataFrame({"n_inst": gi.size(), "ws10": gi["ws10"].mean(), "blh": gi["blh_m"].mean(),
                      "vc": gi["vc"].mean(), "t2m": gi["t2m_c"].mean(), "rh": gi["rh_pct"].mean()})
    ga = h.groupby("day_accum")
    d = d.join(pd.DataFrame({"n_acc": ga.size(), "tp_mm": ga["tp_mm"].sum()}), how="outer")
    d = d[d["n_inst"].eq(24) & d["n_acc"].eq(24)].drop(columns=["n_inst", "n_acc"])
    d["rain_day"] = (d["tp_mm"] >= 1.0).astype(float)
    d["log_vc"] = np.log(d["vc"])
    d.index.name = "date"
    return d.reset_index()


# ------------------------------------------------------------------ fire exposure

def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(lat1)[:, None], np.radians(lat2)[None, :]
    dphi = p2 - p1
    dl = np.radians(lon2)[None, :] - np.radians(lon1)[:, None]
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * ff.EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def endpoint_table(ends: pd.DataFrame) -> pd.DataFrame:
    e = ends[ends["hour_back"].between(1, 72)].copy()
    e["point_date"] = (pd.to_datetime(e["point_time_utc"], utc=True).dt.tz_convert(TZ)
                       .dt.tz_localize(None).dt.normalize())
    e["arrival_date"] = e["arrival_utc"].dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    return e[["arrival_date", "point_date", "lat", "lon", "height_m_agl"]]


def fire_exposure(endpoints: pd.DataFrame, fires: pd.DataFrame, buffers=(FIRE_BUFFER_KM,),
                  max_height: float | None = FIRE_MAX_HEIGHT_M, date_shift_years: int = 0) -> pd.DataFrame:
    """Total FRP (MW) of unique detections intercepted by each day's trajectory, per buffer.

    A detection is intercepted if it lies within `buffer` km of an endpoint (height <= max_height,
    unless None) and its PKT date equals the endpoint's PKT date or the day before. With
    date_shift_years = s, detections from date D are treated as if they occurred on D + s years."""
    f = fires[["date_pkt", "latitude", "longitude", "frp"]].copy()
    if date_shift_years:
        f["date_pkt"] = f["date_pkt"] + pd.DateOffset(years=date_shift_years)
    f = f.reset_index(drop=True)
    by_date = {d: g for d, g in f.groupby("date_pkt")}
    e = endpoints if max_height is None else endpoints[endpoints["height_m_agl"] <= max_height]
    rows = []
    for day, ep in e.groupby("arrival_date"):
        cand_dates = sorted(set(ep["point_date"]) | set(ep["point_date"] - pd.Timedelta(days=1)))
        cand = [by_date[d] for d in cand_dates if d in by_date]
        rec = {"date": day}
        if not cand:
            rec.update({f"fe_{int(b)}km": 0.0 for b in buffers})
            rows.append(rec)
            continue
        c = pd.concat(cand)
        dist = haversine_km(ep["lat"].to_numpy(), ep["lon"].to_numpy(), c["latitude"].to_numpy(), c["longitude"].to_numpy())
        pdates = ep["point_date"].to_numpy()[:, None]
        fdates = c["date_pkt"].to_numpy()[None, :]
        date_ok = (fdates == pdates) | (fdates == pdates - np.timedelta64(1, "D"))
        for b in buffers:
            hit = ((dist <= b) & date_ok).any(axis=0)
            rec[f"fe_{int(b)}km"] = float(c["frp"].to_numpy()[hit].sum())
        rows.append(rec)
    out = pd.DataFrame(rows)
    # days whose trajectory had no endpoint below the height cap: exposure 0 (no interception possible)
    all_days = pd.DataFrame({"date": sorted(endpoints["arrival_date"].unique())})
    return all_days.merge(out, on="date", how="left").fillna(0.0)


def missing_satellite_days(snpp: pd.DataFrame, noaa20: pd.DataFrame) -> set:
    near_s = snpp[snpp["dist_km"] < ff.MAX_KM].groupby("date_pkt").size()
    near_n = noaa20[noaa20["dist_km"] < ff.MAX_KM].groupby("date_pkt").size()
    days = near_n[near_n >= MISSING_SAT_NOAA20_MIN].index
    return {d for d in days if near_s.get(d, 0) == 0}


def exposure_missing_mask(endpoints: pd.DataFrame, missing_days: set) -> pd.Series:
    """True for trajectory days that use (endpoint date or the day before) a missing satellite day."""
    e = endpoints.copy()
    e["uses_missing"] = e["point_date"].isin(missing_days) | (e["point_date"] - pd.Timedelta(days=1)).isin(missing_days)
    return e.groupby("arrival_date")["uses_missing"].any()


# ------------------------------------------------------------------ resampling

def block_bootstrap_indices(groups: np.ndarray, rng: np.random.Generator, block: int = BLOCK_DAYS) -> np.ndarray:
    """Moving-block bootstrap of row positions: within each group (rows already in date order),
    draw ceil(n/block) blocks of `block` consecutive rows with random starts; truncate to n."""
    out = []
    for g in pd.unique(groups):
        pos = np.flatnonzero(groups == g)
        n = len(pos)
        if n <= block:
            out.append(pos[rng.integers(0, n, n)])
            continue
        starts = rng.integers(0, n - block + 1, int(np.ceil(n / block)))
        take = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        out.append(pos[take])
    return np.concatenate(out)


def block_permute(values: np.ndarray, groups: np.ndarray, rng: np.random.Generator, block: int = BLOCK_DAYS) -> np.ndarray:
    """Shuffle the order of consecutive `block`-length chunks of `values` within each group."""
    out = values.copy()
    for g in pd.unique(groups):
        pos = np.flatnonzero(groups == g)
        chunks = [pos[i:i + block] for i in range(0, len(pos), block)]
        order = rng.permutation(len(chunks))
        out[pos] = np.concatenate([values[chunks[o]] for o in order])
    return out


def between_variance(y: np.ndarray, labels: np.ndarray) -> float:
    m = y.mean()
    return float(sum((labels == c).sum() * (y[labels == c].mean() - m) ** 2 for c in np.unique(labels)) / len(y))


def ols(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, adj, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        adj[k] = run
    return adj


# ------------------------------------------------------------------ design matrices

def dummies(labels: np.ndarray, levels: list, ref) -> np.ndarray:
    return np.column_stack([(labels == lv).astype(float) for lv in levels if lv != ref]) if len(levels) > 1 else np.empty((len(labels), 0))


def cluster_levels(d: pd.DataFrame, col: str = "cluster") -> tuple[np.ndarray, list, object]:
    """Clusters with >= MIN_CELL_DAYS days are separate levels; smaller ones are merged into
    'other' for adjustment; the reference is the most frequent level."""
    counts = d[col].value_counts()
    big = counts[counts >= MIN_CELL_DAYS].index
    lab = np.where(d[col].isin(big), d[col].astype(str), "other")
    levels = list(pd.Series(lab).value_counts().index)
    return lab, levels, levels[0]


def fit_with_ci(d: pd.DataFrame, build, rng: np.random.Generator, block: int = BLOCK_DAYS, n_boot: int = N_BOOT):
    """Point estimate from build(d) -> vector, and 2.5/97.5 percentiles over block-bootstrap refits."""
    est = build(d)
    g = d["season_year"].to_numpy()
    reps = []
    for _ in range(n_boot):
        idx = block_bootstrap_indices(g, rng, block)
        try:
            reps.append(build(d.iloc[idx]))
        except (np.linalg.LinAlgError, ValueError, KeyError):
            continue
    reps = np.array([r for r in reps if r is not None and len(r) == len(est)])
    lo, hi = np.nanpercentile(reps, [2.5, 97.5], axis=0)
    return est, lo, hi, len(reps)


# ------------------------------------------------------------------ hypothesis tests

def h1_season(d: pd.DataFrame, rng: np.random.Generator, outcome: str = "log_pm", adjust: list | None = None,
              block: int = BLOCK_DAYS) -> pd.DataFrame:
    """Ratios of geometric means of each tested cluster vs the reference (most frequent), within
    one season, optionally adjusted for covariates. Clusters with < MIN_CELL_DAYS days are not tested."""
    counts = d["cluster"].value_counts()
    tested = sorted(counts[counts >= MIN_CELL_DAYS].index)
    dd = d[d["cluster"].isin(tested)].copy()
    if len(tested) < 2:
        return pd.DataFrame()
    ref = int(counts.loc[tested].idxmax())
    others = [c for c in tested if c != ref]

    def build(x):
        present = set(x["cluster"].unique())
        if ref not in present or any(c not in present for c in others):
            raise ValueError("a cluster is absent from this resample")
        X = [np.ones(len(x))] + [(x["cluster"].to_numpy() == c).astype(float) for c in others]
        if adjust:
            X += [x[a].to_numpy(float) for a in adjust]
        b = ols(x[outcome].to_numpy(float), np.column_stack(X))
        return b[1:1 + len(others)]

    est, lo, hi, n = fit_with_ci(dd, build, rng, block)
    return pd.DataFrame({"cluster": others, "ref_cluster": ref, "n_days": [int(counts[c]) for c in others],
                         "ratio": np.exp(est), "ci_low": np.exp(lo), "ci_high": np.exp(hi), "boot_ok": n})


def h1_permutation(d: pd.DataFrame, rng: np.random.Generator) -> tuple[float, float]:
    counts = d["cluster"].value_counts()
    dd = d[d["cluster"].isin(counts[counts >= MIN_CELL_DAYS].index)]
    y, lab, g = dd["log_pm"].to_numpy(), dd["cluster"].to_numpy(), dd["season_year"].to_numpy()
    obs = between_variance(y, lab)
    null = np.array([between_variance(y, block_permute(lab, g, rng)) for _ in range(N_PERM)])
    return obs, float((1 + (null >= obs).sum()) / (1 + N_PERM))


def h1b_season(d: pd.DataFrame, rng: np.random.Generator, block: int = BLOCK_DAYS) -> tuple:
    q = d["traj_mean_dist72_km"].quantile([1 / 3, 2 / 3]).to_numpy()
    terc = np.where(d["traj_mean_dist72_km"] <= q[0], 1, np.where(d["traj_mean_dist72_km"] <= q[1], 2, 3))
    dd = d.assign(tercile=terc)
    dd = dd[dd["tercile"].isin([1, 3])]

    def build(x):
        a, b = x.loc[x["tercile"] == 1, "log_pm"], x.loc[x["tercile"] == 3, "log_pm"]
        if not len(a) or not len(b):
            raise ValueError("empty tercile")
        return np.array([a.mean() - b.mean()])

    est, lo, hi, _ = fit_with_ci(dd, build, rng, block)
    return float(np.exp(est[0])), float(np.exp(lo[0])), float(np.exp(hi[0])), q


def h2_season(d: pd.DataFrame, rng: np.random.Generator, block: int = BLOCK_DAYS) -> dict:
    lab, levels, ref = cluster_levels(d)
    dd = d.assign(clab=lab)

    def m1(x):
        return ols(x["log_pm"].to_numpy(), np.column_stack([np.ones(len(x)), x["log_vc"].to_numpy()]))[1:2]

    def m2(x):
        X = np.column_stack([np.ones(len(x)), x["log_vc"].to_numpy(), dummies(x["clab"].to_numpy(), levels, ref)])
        return ols(x["log_pm"].to_numpy(), X)[1:2]

    e1, l1, h1_, _ = fit_with_ci(dd, m1, rng, block)
    e2, l2, h2_, _ = fit_with_ci(dd, m2, rng, block)
    return {"b_model1": e1[0], "ci1": [l1[0], h1_[0]], "b_model2": e2[0], "ci2": [l2[0], h2_[0]]}


def h3_fit(d: pd.DataFrame, fe_col: str, levels: list, ref, years: list) -> np.ndarray:
    X = np.column_stack([np.ones(len(d)), d["log_vc"].to_numpy(), dummies(d["clab"].to_numpy(), levels, ref),
                         d["doy_on"].to_numpy(float)] + [(d["year"].to_numpy() == y).astype(float) for y in years[1:]]
                        + [np.log1p(d[fe_col].to_numpy(float))])
    return ols(d["log_pm"].to_numpy(), X)[-1:]


# ------------------------------------------------------------------ CWT

def cwt_grid(endpoints: pd.DataFrame, day_values: pd.Series, grid: float = CWT_GRID_DEG) -> pd.DataFrame:
    """Concentration-weighted trajectory field: mean daily PM2.5 over endpoints in each cell,
    times openair-style weights by endpoint count (>80: 1, 20-80: 0.7, 10-20: 0.42, <10: 0.05)."""
    e = endpoints[endpoints["arrival_date"].isin(day_values.index)].copy()
    e["c"] = e["arrival_date"].map(day_values)
    e["ix"] = np.floor(e["lon"] / grid) * grid
    e["iy"] = np.floor(e["lat"] / grid) * grid
    g = e.groupby(["ix", "iy"]).agg(n=("c", "size"), cwt=("c", "mean")).reset_index()
    g["w"] = np.select([g["n"] > 80, g["n"] > 20, g["n"] > 10], [1.0, 0.7, 0.42], 0.05)
    g["wcwt"] = g["w"] * g["cwt"]
    return g


# ------------------------------------------------------------------ main

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    days, traj, ends = load_days()

    # 1. clustering (all trajectories)
    cl = ward_clusters(traj)
    k = cl["k"]
    lab_k, summ = relabel_and_name(traj, cl["labels"][k])
    traj = traj.assign(cluster=lab_k)
    alt = {}
    for kk in (k - 1, k + 1):
        alt[kk], _ = relabel_and_name(traj, cl["labels"][kk])
    pd.DataFrame({"k": list(cl["tsv"].index), "tsv": cl["tsv"].values}).merge(
        pd.DataFrame({"k": list(cl["delta"].index), "delta_pct": cl["delta"].values}), on="k", how="left").merge(
        pd.DataFrame({"k": list(cl["silhouette"]), "silhouette": list(cl["silhouette"].values())}), on="k", how="left"
    ).to_csv(OUT_DIR / "cluster_choice.csv", index=False)
    summ.to_csv(OUT_DIR / "cluster_summary.csv", index=False)
    mean_paths = traj.groupby("cluster")[tf.shape_columns()].mean()
    mean_paths.to_csv(OUT_DIR / "cluster_mean_paths_km.csv")
    traj_days = traj.reset_index()[["date_pkt", "cluster"]].rename(columns={"date_pkt": "date"})
    for kk, lab in alt.items():
        traj_days[f"cluster_k{kk}"] = lab
    monthly = traj.assign(month=traj["date_pkt"].dt.month).groupby(["month", "cluster"]).size().unstack(fill_value=0)
    (100 * monthly.div(monthly.sum(axis=1), axis=0)).round(1).to_csv(OUT_DIR / "cluster_frequency_by_month_pct.csv")

    # 2-4. assemble day table
    wx = daily_weather()
    ep = endpoint_table(ends)
    snpp = ff.prepare(ff.load_source(ff.PRIMARY))
    noaa = ff.prepare(ff.load_source(ff.CROSSCHECK))
    miss_days = missing_satellite_days(snpp, noaa)
    fe = fire_exposure(ep, snpp, buffers=(FIRE_BUFFER_KM,) + FIRE_BUFFERS_SENS)
    fe_noh = fire_exposure(ep, snpp, buffers=(FIRE_BUFFER_KM,), max_height=None).rename(columns={"fe_50km": "fe_50km_noheight"})
    miss = exposure_missing_mask(ep, miss_days)
    fe = fe.merge(fe_noh, on="date")
    fe.loc[fe["date"].map(miss).fillna(False).astype(bool), [c for c in fe.columns if c.startswith("fe_")]] = np.nan
    fire_first, fire_last = snpp["date_pkt"].min(), snpp["date_pkt"].max()
    for s in NULL_SHIFTS:
        fs = fire_exposure(ep, snpp, date_shift_years=s).rename(columns={"fe_50km": f"fe_null_{s:+d}"})
        src_dates = fs["date"] - pd.DateOffset(years=s)
        ok = (src_dates >= fire_first + pd.Timedelta(days=4)) & (src_dates <= fire_last)
        fs.loc[~ok, f"fe_null_{s:+d}"] = np.nan
        fe = fe.merge(fs, on="date", how="left")

    d = (days.merge(traj_days, on="date", how="left").merge(wx, on="date", how="left").merge(fe, on="date", how="left"))
    d = d.dropna(subset=["log_vc", "ws10", "t2m", "rh", "rain_day"]).reset_index(drop=True)
    # day-of-year climatology anomaly (+-15 calendar days, circular, all years)
    doy = d["doy"].to_numpy()
    diff = np.abs(doy[:, None] - doy[None, :])
    win = np.minimum(diff, 366 - diff) <= CLIM_HALF_WINDOW
    d["clim"] = (win * d["log_pm"].to_numpy()[None, :]).sum(axis=1) / win.sum(axis=1)
    d["anom"] = d["log_pm"] - d["clim"]
    d.to_csv(OUT_DIR / "analysis_days.csv", index=False)

    summary = {"predeclaration": "results/tables/stage7_association_predeclaration.md", "analysis_days": len(d),
               "trajectories": len(traj), "k": k, "kmeans_ari": round(cl["kmeans_ari"], 3),
               "missing_satellite_days": sorted(str(x.date()) for x in miss_days),
               "fire_days_missing_exposure": int(d["fe_50km"].isna().sum()),
               "days_by_season": d["season"].value_counts().reindex(SEASON_ORDER).to_dict()}

    # descriptive: PM by cluster x season
    desc = d.groupby(["season", "cluster"])["pm25_daily_mean"].agg(n="size", median="median", mean="mean",
                                                                   q25=lambda s: s.quantile(.25), q75=lambda s: s.quantile(.75))
    desc.round(1).to_csv(OUT_DIR / "pm_by_season_cluster.csv")

    # 5. tests
    rows_h1, perm, rows_b, rows_h2, ladder, sens = [], {}, [], [], [], []
    adjust = ["log_vc", "ws10", "t2m", "rh", "rain_day"]
    for s in SEASON_ORDER:
        ds = d[d["season"] == s].sort_values("date")
        r = h1_season(ds, rng)
        if len(r):
            rows_h1.append(r.assign(season=s))
            for rung, out_col, adj in [("a_raw", "log_pm", None), ("b_anomaly", "anom", None), ("c_weather_adjusted", "log_pm", adjust)]:
                ladder.append(h1_season(ds, rng, outcome=out_col, adjust=adj).assign(season=s, rung=rung))
            for kk in (k - 1, k + 1):
                sens.append(h1_season(ds.assign(cluster=ds[f"cluster_k{kk}"]), rng).assign(season=s, check=f"k={kk}"))
            for blk in BLOCK_CHECKS:
                sens.append(h1_season(ds, rng, block=blk).assign(season=s, check=f"block={blk}d"))
            perm[s] = h1_permutation(ds, rng)
        ratio, lo, hi, q = h1b_season(ds, rng)
        rows_b.append({"season": s, "n_days": len(ds), "tercile_cuts_km": [round(x) for x in q],
                       "ratio_shortest_vs_longest": ratio, "ci_low": lo, "ci_high": hi})
        h2r = h2_season(ds, rng)
        rows_h2.append({"season": s, "n_days": len(ds), **h2r})
    # secondary season split: October-January
    doj = d[d["oct_jan"]].sort_values("date")
    rows_h1.append(h1_season(doj, rng).assign(season="Oct-Jan (secondary)"))
    perm["Oct-Jan (secondary)"] = h1_permutation(doj, rng)
    padj = holm({s: perm[s][1] for s in SEASON_ORDER if s in perm})
    pd.concat(rows_h1).to_csv(OUT_DIR / "h1_cluster_ratios.csv", index=False)
    pd.DataFrame([{"season": s, "between_var": v[0], "p_perm": v[1], "p_holm": padj.get(s)} for s, v in perm.items()]
                 ).to_csv(OUT_DIR / "h1_permutation.csv", index=False)
    pd.concat(ladder).to_csv(OUT_DIR / "h1_confounding_ladder.csv", index=False)
    pd.concat(sens).to_csv(OUT_DIR / "h1_sensitivity.csv", index=False)
    pd.DataFrame(rows_b).to_csv(OUT_DIR / "h1b_stagnation_terciles.csv", index=False)
    pd.DataFrame(rows_h2).to_csv(OUT_DIR / "h2_ventilation.csv", index=False)

    # H3: October-November days
    on = d[d["season"] == "post-monsoon"].sort_values("date").copy()
    lab, levels, ref = cluster_levels(on)
    on["clab"] = lab
    on["doy_on"] = on["doy"] - 274
    h3_rows = []
    for fe_col, label in [("fe_50km", "primary (50 km, <=1,500 m)"), ("fe_25km", "buffer 25 km"),
                          ("fe_100km", "buffer 100 km"), ("fe_50km_noheight", "no height filter")]:
        sub = on.dropna(subset=[fe_col])
        years = sorted(sub["year"].unique())
        est, lo, hi, nb = fit_with_ci(sub, lambda x, c=fe_col, yrs=years: h3_fit(x, c, levels, ref, yrs), rng)
        h3_rows.append({"exposure": label, "n_days": len(sub), "c": est[0], "ci_low": lo[0], "ci_high": hi[0],
                        "ratio_per_doubling_of_1plusFE": float(np.exp(est[0] * np.log(2)))})
    for blk in BLOCK_CHECKS:
        sub = on.dropna(subset=["fe_50km"]); years = sorted(sub["year"].unique())
        est, lo, hi, _ = fit_with_ci(sub, lambda x, yrs=years: h3_fit(x, "fe_50km", levels, ref, yrs), rng, block=blk)
        h3_rows.append({"exposure": f"primary, block={blk}d", "n_days": len(sub), "c": est[0], "ci_low": lo[0], "ci_high": hi[0]})
    nulls = {}
    for s_ in NULL_SHIFTS:
        col = f"fe_null_{s_:+d}"
        sub = on.dropna(subset=[col])
        if len(sub) < 60:
            continue
        years = sorted(sub["year"].unique())
        nulls[s_] = float(h3_fit(sub, col, levels, ref, years)[0])
    c_primary = h3_rows[0]["c"]
    h3 = pd.DataFrame(h3_rows)
    h3.to_csv(OUT_DIR / "h3_fire_exposure.csv", index=False)
    pd.DataFrame({"shift_years": list(nulls), "c_null": list(nulls.values())}).to_csv(OUT_DIR / "h3_null_shifts.csv", index=False)
    summary["h3_null_share_ge_c"] = float(np.mean([v >= c_primary for v in nulls.values()])) if nulls else None
    summary["h3_null_count"] = len(nulls)

    # 6. CWT (post-monsoon and winter)
    for s in ["post-monsoon", "winter"]:
        vals = d[d["season"] == s].set_index("date")["pm25_daily_mean"]
        cwt_grid(ep, vals).to_csv(OUT_DIR / f"cwt_{s}.csv", index=False)

    (OUT_DIR / "stage7_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
