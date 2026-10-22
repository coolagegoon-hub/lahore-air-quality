"""Unit tests for src.stage1c_analysis and src.airnow_archive using synthetic inputs only."""

import numpy as np
import pandas as pd
import pytest

from src import airnow_archive as aa
from src import pm25_qc as qc
from src import stage1c_analysis as s1c


def _grid(values, start="2021-01-04 01:00"):
    """Hourly grid (hour-ending PKT labels) built through the real Stage 1B pipeline."""
    ts = pd.date_range(pd.Timestamp(start, tz=qc.TZ), periods=len(values), freq="h")
    raw = pd.DataFrame({
        "location_id": "1", "sensors_id": "1", "lat": "0", "lon": "0", "source_file": "f",
        "parameter": "pm25", "units": "µg/m³",
        "datetime": [t.isoformat() for t in ts], "value": [str(v) for v in values],
    })
    hourly, _ = qc.resolve_duplicate_timestamps(qc.parse_hourly(raw))
    return qc.flag_repeats(qc.to_complete_hourly_grid(hourly))


def test_repeat_runs_lengths_values_and_times():
    g = _grid([1, 5, 5, 5, 2, -999, 2, 7, 7])
    runs = s1c.repeat_runs(g)
    assert runs["length_h"].tolist() == [3, 2]
    assert runs["value"].tolist() == [5.0, 7.0]
    assert runs.loc[0, "first_hour_end"] == pd.Timestamp("2021-01-04 02:00", tz=qc.TZ)
    assert runs.loc[0, "last_hour_end"] == pd.Timestamp("2021-01-04 04:00", tz=qc.TZ)
    assert runs.loc[0, "first_hour_start"] == pd.Timestamp("2021-01-04 01:00", tz=qc.TZ)


def test_exclude_runs_removes_whole_run_only_at_threshold_and_keeps_original():
    g = _grid([1] + [9] * 6 + [2] + [4] * 5 + [3])
    out6 = s1c.exclude_runs(g, 6)
    assert int(out6["excluded_by_run_rule"].sum()) == 6          # the 6-hour run, incl. first hour
    assert out6.loc[out6["value"] == 9, "valid"].eq(False).all()
    assert out6.loc[out6["value"] == 4, "valid"].all()            # 5-hour run untouched
    assert int(s1c.exclude_runs(g, 7)["excluded_by_run_rule"].sum()) == 0
    assert int(s1c.exclude_runs(g, None)["excluded_by_run_rule"].sum()) == 0
    assert g["valid"].all()                                        # input grid not modified


def _daily(complete_flags, start="2021-12-27", means=None):
    idx = pd.date_range(start, periods=len(complete_flags), freq="D", name="date")
    means = means if means is not None else np.arange(1, len(complete_flags) + 1, dtype=float)
    d = pd.DataFrame({"complete": complete_flags}, index=idx)
    d["pm25_daily_mean"] = np.where(d["complete"], means, np.nan)
    return d


def test_weekly_completeness_thursday_year_season_and_partial_weeks():
    # Mon 2021-12-27 .. Sun 2022-01-09 (two full weeks) + Mon 2022-01-10 (partial, dropped)
    flags = [True] * 7 + [True, True, False, True, True, True, False] + [True]
    wk = s1c.weekly_completeness(_daily(flags))
    assert len(wk) == 2
    # week of 2021-12-27: Thursday 2021-12-30 -> year 2021, season 2021-22
    assert wk["year"].tolist() == [2021, 2022]
    assert wk["smog_season"].tolist() == ["2021-22", "2021-22"]
    assert wk["complete_days"].tolist() == [7, 5]
    counts = s1c.weekly_threshold_counts(wk, "smog_season")
    assert counts.loc["2021-22", ["weeks_ge_7_of_7", "weeks_ge_6_of_7", "weeks_ge_5_of_7"]].tolist() == [1, 1, 2]


def test_non_smog_weeks_have_no_season():
    wk = s1c.weekly_completeness(_daily([True] * 7, start="2021-06-07"))
    assert wk["smog_season"].tolist() == [""]


def test_missing_day_error_exhaustive_and_zero_for_constant_week():
    d = _daily([True] * 7, start="2021-06-07", means=np.full(7, 50.0))
    wk = s1c.weekly_completeness(d)
    e = s1c.missing_day_error(d, wk)
    assert e["n_subsets"].tolist() == [7, 21]                     # C(7,1), C(7,2)
    assert (e["max_abs_pct_error"] == 0).all()

    d2 = _daily([True] * 7, start="2021-06-07", means=np.array([10, 10, 10, 10, 10, 10, 80.0]))
    e2 = s1c.missing_day_error(d2, s1c.weekly_completeness(d2))
    # true mean 20; dropping the 80 day gives 10 -> 50% error, the largest possible for k=1
    assert e2.loc[(1, False), "max_abs_pct_error"] == pytest.approx(50.0)


def test_lag_alignment_detects_one_hour_shift():
    idx = pd.date_range(pd.Timestamp("2021-01-01 01:00", tz=qc.TZ), periods=48, freq="h")
    airnow = pd.Series(np.arange(48, dtype=float) * 3 + 1, index=idx)
    openaq = pd.Series(airnow.to_numpy()[1:], index=idx[:-1])     # OpenAQ(t) = AirNow(t+1)
    lags = s1c.lag_alignment(openaq, airnow).set_index("lag_h")["pct_equal"]
    assert lags[1] == 100.0 and lags[0] == 0.0


def test_airnow_hourly_converts_begin_gmt_to_hour_ending_pkt(tmp_path, monkeypatch):
    """A record at 19:00 GMT (period 19:00-19:59 GMT) is 00:00-00:59 PKT -> hour-ending 01:00 PKT."""
    monkeypatch.setattr(aa, "CACHE_DIR", tmp_path)
    line = "09/14/21|19:00|586PK3010003|Lahore|5|PM2.5|UG/M3|43|U.S. Department of State Pakistan - Lahore\n"

    def fake_fetch(url, needle, retries=4):
        return line if url.endswith("HourlyData_2021091419.dat") else None

    monkeypatch.setattr(aa, "_fetch_lines", fake_fetch)
    df = aa.hourly("586PK3010003", "2021-09-14", "2021-09-14", workers=2)
    assert len(df) == 1
    assert df.loc[0, "period_end_local"] == pd.Timestamp("2021-09-15 01:00", tz="Asia/Karachi")
    assert df.attrs["files_missing"] == 23
    # second call is served from the cache (including cached "missing" markers)
    monkeypatch.setattr(aa, "_fetch_lines", lambda *a, **k: pytest.fail("network used despite cache"))
    assert len(aa.hourly("586PK3010003", "2021-09-14", "2021-09-14", workers=2)) == 1


# ---------------------------------------------------------------- src.airnow_bulk

class _FakeResp:
    def __init__(self, data, clen):
        self._data, self.headers = data, {"Content-Length": str(clen)}

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_verified_writes_only_site_lines_when_sizes_match(tmp_path, monkeypatch):
    from src import airnow_bulk as ab
    monkeypatch.setattr(aa, "CACHE_DIR", tmp_path)
    data = b"a|586PK3010003|x\nb|OTHER|y\n"
    monkeypatch.setattr(ab.urllib.request, "urlopen", lambda *a, **k: _FakeResp(data, len(data)))
    r = ab.fetch_verified("airnow/2021/20210915/HourlyData_2021091500.dat", len(data), "586PK3010003")
    assert r["status"] == "downloaded_verified" and r["n_lines"] == 1
    assert (tmp_path / "586PK3010003/2021/20210915/HourlyData_2021091500.dat").read_text() == "a|586PK3010003|x\n"
    # a second call uses the cache and does not touch the network
    monkeypatch.setattr(ab.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network used"))
    assert ab.fetch_verified("airnow/2021/20210915/HourlyData_2021091500.dat", len(data), "586PK3010003")["status"] == "cached_unverified"


def test_fetch_verified_rejects_truncated_file_and_writes_no_cache(tmp_path, monkeypatch):
    from src import airnow_bulk as ab
    monkeypatch.setattr(aa, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(ab.time, "sleep", lambda s: None)
    data = b"a|586PK3010003|x\n"
    monkeypatch.setattr(ab.urllib.request, "urlopen", lambda *a, **k: _FakeResp(data, len(data)))
    r = ab.fetch_verified("airnow/2021/20210915/HourlyData_2021091501.dat", len(data) + 100, "586PK3010003")
    assert r["status"] == "FAILED_size"
    assert not (tmp_path / "586PK3010003/2021/20210915/HourlyData_2021091501.dat").exists()
