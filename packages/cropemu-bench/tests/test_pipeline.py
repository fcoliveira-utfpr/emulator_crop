import numpy as np
import pandas as pd

from cropemu_bench.pipeline import _daily_table


def test_daily_table_keys_by_sample_and_drops_days_before_sowing():
    raw = pd.DataFrame({"treatment": [0, 0, 0, 1, 1], "season": [0] * 5, "YEAR": [2019] * 5,
                        "DOY": [300, 301, 302, 300, 301], "DAP": ["-1", "0", "1", "0", "1"],
                        "LAID": ["0", "0.01", "0.02", "0", "-99"]})
    d = _daily_table(raw, ["DAP", "LAID"], samples=np.array([10, 11]))
    assert list(d.columns) == ["sample", "DAP", "LAID"]
    assert d["sample"].tolist() == [10, 10, 11, 11]
    assert d["DAP"].dtype == "int16" and d["LAID"].dtype == "float32"
    assert np.allclose(d["LAID"].to_numpy()[:3], [0.01, 0.02, 0])
    assert np.isnan(d["LAID"].iloc[3])                     # DSSAT's -99: missing


def test_daily_table_aquacrop_missing_code():
    raw = pd.DataFrame({"treatment": [0, 0], "DAP": [-9, 5], "StExp": [-9, -9], "CC": [0, 12.5]})
    d = _daily_table(raw, ["DAP", "StExp", "CC"], samples=np.array([3]), missing=-9)
    assert len(d) == 1 and np.isnan(d["StExp"].iloc[0]) and d["CC"].iloc[0] == np.float32(12.5)


def test_aquacrop_crop_days_count_calendar_days_through_a_germination_delay():
    from cropemu_bench.pipeline_aquacrop import crop_days
    # sown 1 Nov; dry topsoil: AquaCrop keeps DAP 0 for 2 days, restarts, and writes -9 after the cycle
    day = pd.DataFrame({"treatment": 0, "Year": 2019, "Month": 11, "Day": [1, 2, 3, 4, 5, 6],
                        "DAP": [0, 0, 1, 2, 3, -9], "Stage": [1, 1, 1, 2, 4, 0]})
    c = crop_days(day)
    assert c["DAP"].tolist() == [1, 2, 3, 4, 5]
