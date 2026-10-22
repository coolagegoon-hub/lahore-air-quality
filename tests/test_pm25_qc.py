"""Unit tests for src.pm25_qc using small synthetic inputs (no real data)."""

import numpy as np
import pandas as pd
import pytest

from src import pm25_qc as qc


def _raw(timestamps, values, units="µg/m³"):
    return pd.DataFrame(
        {
            "location_id": "1",
            "sensors_id": "1",
            "lat": "0",
            "lon": "0",
            "source_file": "f",
            "parameter": "pm25",
            "units": units,
            "datetime": timestamps,
            "value": [str(v) for v in values],
        }
    )


def _day_ts(date="2021-01-01"):
    """24 hour-ending timestamps for one local day: 01:00 ... 00:00 next day."""
    start = pd.Timestamp(f"{date} 01:00", tz=qc.TZ)
    return [t.isoformat() for t in pd.date_range(start, periods=24, freq="h")]


def _pipeline(raw):
    hourly, _ = qc.resolve_duplicate_timestamps(qc.parse_hourly(raw))
    grid = qc.flag_repeats(qc.to_complete_hourly_grid(hourly))
    return grid, qc.daily_summary(grid)


def test_negative_fill_values_are_invalid():
    df = qc.parse_hourly(_raw(_day_ts()[:3], [10, -999, -1]))
    assert df["valid"].tolist() == [True, False, False]


def test_unexpected_units_raise():
    with pytest.raises(ValueError):
        qc.parse_hourly(_raw(_day_ts()[:1], [10], units="ppm"))


def test_hour_ending_midnight_belongs_to_previous_day():
    idx = pd.DatetimeIndex(pd.to_datetime(["2021-01-02T00:00:00+05:00", "2021-01-02T01:00:00+05:00"])).tz_convert(qc.TZ)
    days = qc.assign_day(idx, "hour_ending")
    assert list(days.strftime("%Y-%m-%d")) == ["2021-01-01", "2021-01-02"]


@pytest.mark.parametrize("n_valid, complete", [(17, False), (18, True), (24, True)])
def test_18_of_24_completeness_boundary(n_valid, complete):
    values = list(range(1, 25))
    values = [v if i < n_valid else -999 for i, v in enumerate(values)]
    _, daily = _pipeline(_raw(_day_ts(), values))
    row = daily.loc[pd.Timestamp("2021-01-01")]
    assert row["hours_valid"] == n_valid
    assert bool(row["complete"]) is complete
    expected = np.mean(range(1, n_valid + 1))
    assert row["mean_all_valid_hours"] == pytest.approx(expected)
    if complete:
        assert row["pm25_daily_mean"] == pytest.approx(expected)
    else:
        assert np.isnan(row["pm25_daily_mean"])


def test_missing_rows_count_as_invalid_hours():
    ts = _day_ts()
    keep = [0] + list(range(7, 24))  # 18 rows present, hours 2-7 absent from source
    _, daily = _pipeline(_raw([ts[i] for i in keep], [5] * len(keep)))
    row = daily.loc[pd.Timestamp("2021-01-01")]
    assert row["hours_in_grid"] == 24
    assert row["hours_present"] == 18
    assert row["hours_valid"] == 18


def test_repeats_detected_only_between_adjacent_valid_hours():
    # 10,10 repeat; -999 breaks adjacency; 20 after gap is not a repeat of 20 before gap
    grid, _ = _pipeline(_raw(_day_ts()[:6], [10, 10, 20, -999, 20, 30]))
    assert grid["repeat_prev"].tolist() == [False, True, False, False, False, False]
    assert grid["repeat_run_length"].tolist()[:2] == [2, 2]


def test_duplicate_timestamps_identical_kept_conflicting_invalidated():
    ts = _day_ts()[:2]
    raw = _raw([ts[0], ts[0], ts[1], ts[1]], [10, 10, 20, 25])
    hourly, stats = qc.resolve_duplicate_timestamps(qc.parse_hourly(raw))
    assert stats["duplicate_timestamps_identical"] == 1
    assert stats["duplicate_timestamps_conflicting"] == 1
    assert hourly["valid"].tolist() == [True, False]
