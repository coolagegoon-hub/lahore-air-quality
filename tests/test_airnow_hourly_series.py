"""Unit tests for src.airnow_hourly_series using synthetic inputs only."""

import numpy as np
import pandas as pd
import pytest

from src import airnow_hourly_series as ahs
from src import pm25_qc as qc


def _rows(begins_utc, values, units="UG/M3", offset="5", aqsid=ahs.AQSID):
    begin = pd.DatetimeIndex(pd.to_datetime(begins_utc, utc=True))
    return pd.DataFrame({
        "aqsid": aqsid, "parameter": "PM2.5", "units": units, "gmt_offset": offset,
        "value": np.asarray(values, dtype=float),
        "period_begin_utc": begin,
        "period_end_local": (begin + pd.Timedelta(hours=1)).tz_convert(qc.TZ),
    })


def test_local_range_is_hour_ending_and_complete():
    r = ahs.local_hour_ending_range("2021-01-01", "2021-01-02")
    assert len(r) == 48
    assert r[0] == pd.Timestamp("2021-01-01 01:00", tz=qc.TZ)
    assert r[-1] == pd.Timestamp("2021-01-03 00:00", tz=qc.TZ)


def test_gmt_dates_cover_local_days():
    # local 2021-01-01 begins at 2020-12-31 19:00 GMT; local 2021-01-02 ends at 2021-01-02 18:59 GMT
    assert ahs.gmt_dates_for_local_days("2021-01-01", "2021-01-02") == ("2020-12-31", "2021-01-02")


@pytest.mark.parametrize("kwargs", [{"units": "PPB"}, {"offset": "6"}])
def test_validate_rejects_unexpected_units_or_offset(kwargs):
    with pytest.raises(ValueError):
        ahs.validate_airnow_rows(_rows(["2021-01-01 00:00"], [10], **kwargs))


def test_validate_rejects_duplicate_hours_and_drops_other_sites():
    with pytest.raises(ValueError):
        ahs.validate_airnow_rows(_rows(["2021-01-01 00:00", "2021-01-01 00:00"], [10, 11]))
    mixed = pd.concat([_rows(["2021-01-01 00:00"], [10]), _rows(["2021-01-01 00:00"], [99], aqsid="OTHER")])
    assert len(ahs.validate_airnow_rows(mixed)) == 1


def test_begin_gmt_19h_becomes_hour_ending_01h_pkt_and_belongs_to_that_day():
    h = ahs.to_hourly(_rows(["2020-12-31 19:00"], [42]))
    assert h.index[0] == pd.Timestamp("2021-01-01 01:00", tz=qc.TZ)
    assert qc.assign_day(h.index)[0] == pd.Timestamp("2021-01-01")


def test_negative_policy():
    rows = _rows(["2021-01-01 00:00", "2021-01-01 01:00", "2021-01-01 02:00"], [-3, -6, 5])
    assert ahs.to_hourly(rows, "invalid")["valid"].tolist() == [False, False, True]
    assert ahs.to_hourly(rows, "keep_ge_minus5")["valid"].tolist() == [True, False, True]
    with pytest.raises(ValueError):
        ahs.to_hourly(rows, "something_else")


def test_grid_marks_absent_hours_and_daily_rule_uses_18_of_24():
    labels = ahs.local_hour_ending_range("2021-01-01", "2021-01-02")
    begins = (labels - pd.Timedelta(hours=1)).tz_convert("UTC")
    # day 1: all 24 hours present; day 2: only 17 hours present
    keep = list(range(24)) + list(range(24, 24 + 17))
    h = ahs.to_hourly(_rows(begins[keep], np.arange(len(keep)) + 1.0))
    g = ahs.complete_grid(h, labels)
    assert len(g) == 48 and int(g["present_in_source"].sum()) == 41
    d = qc.daily_summary(g)
    assert d["hours_valid"].tolist() == [24, 17]
    assert d["complete"].tolist() == [True, False]
    assert np.isnan(d.loc[pd.Timestamp("2021-01-02"), "pm25_daily_mean"])


def test_monthly_alignment_labels_shift():
    idx = pd.date_range(pd.Timestamp("2021-03-01 01:00", tz=qc.TZ), periods=24 * 10, freq="h")
    airnow = pd.Series(np.arange(len(idx)) * 1.7 + 3, index=idx)
    aligned = ahs.monthly_alignment(airnow, airnow)
    shifted = ahs.monthly_alignment(pd.Series(airnow.to_numpy()[1:], index=idx[:-1]), airnow)
    assert aligned["label"].tolist() == ["aligned"]
    assert shifted["label"].tolist() == ["shifted_1h_early"]


def _hourly(labels_pkt, values):
    idx = pd.DatetimeIndex(pd.to_datetime(labels_pkt).tz_localize(qc.TZ), name="timestamp")
    v = np.asarray(values, dtype=float)
    return pd.DataFrame({"value": v, "valid": v >= 0}, index=idx)


def test_backfill_fills_only_absent_hours():
    archive = _hourly(["2022-09-05 01:00", "2022-09-05 02:00"], [40, 41])
    back = _hourly(["2022-09-05 02:00", "2022-09-05 03:00", "2022-09-05 04:00"], [41, 42, -2])["value"]
    merged, info = ahs.merge_backfill(archive, back)
    assert list(merged["value"]) == [40, 41, 42, -2]
    assert list(merged["valid"]) == [True, True, True, False]   # negative stays invalid
    assert info == {"backfill_rows": 3, "backfill_overlap_identical": 1, "backfill_hours_added": 2}


def test_backfill_disagreement_stops_the_build():
    archive = _hourly(["2022-09-05 01:00"], [40])
    back = _hourly(["2022-09-05 01:00"], [39])["value"]
    with pytest.raises(ValueError):
        ahs.merge_backfill(archive, back)


def test_load_backfill_skips_missing_rows_and_reads_hour_ending_pkt(tmp_path):
    pd.DataFrame({
        "Site": "Lahore", "Parameter": "PM2.5 - Principal",
        "Date (LT)": ["2022-09-02 02:00 PM", "2022-09-02 03:00 PM", "2022-10-01 12:00 AM"],
        "Raw Conc.": [31.0, -999.0, 105.0], "Conc. Unit": "UG/M3", "Duration": "1 Hr",
        "QC Name": ["Valid", "Missing", "Valid"],
    }).to_csv(tmp_path / "Lahore_PM2.5_2022_09_MTD.csv", index=False)
    s = ahs.load_backfill(tmp_path)
    assert list(s) == [31.0, 105.0]
    assert s.index[0] == pd.Timestamp("2022-09-02 14:00", tz=qc.TZ)
    assert s.index[1] == pd.Timestamp("2022-10-01 00:00", tz=qc.TZ)
