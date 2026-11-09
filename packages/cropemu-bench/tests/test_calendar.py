from datetime import date

import numpy as np
import pandas as pd
import pytest

from cropemu_bench.inputs.calendar import CropCalendar, sowing_dates, sowing_window


def _calendar(tmp_path):
    """A small synthetic GGCMI-like file (0.5° grid over a 3 x 3 cell region)."""
    xr = pytest.importorskip("xarray")
    lat = np.array([-22.75, -23.25, -23.75])
    lon = np.array([-51.75, -51.25, -50.75])
    planting = np.full((3, 3), np.nan, dtype="float32")
    maturity = np.full((3, 3), np.nan, dtype="float32")
    planting[0, 2], maturity[0, 2] = 300, 40                      # only the NE cell has data
    ds = xr.Dataset({"planting_day": (("lat", "lon"), planting), "maturity_day": (("lat", "lon"), maturity),
                     "data_source_used": (("lat", "lon"), np.full((3, 3), 8, dtype="float32"))},
                    coords={"lat": lat, "lon": lon})
    path = tmp_path / "soy_rf.nc4"
    ds.to_netcdf(path)
    return CropCalendar("rf", path=path)


def test_nearest_cell_with_data(tmp_path):
    cal = _calendar(tmp_path)
    e = cal.at(-22.75, -50.75)
    assert (e.planting_doy, e.maturity_doy, e.season_days, e.distance_cells) == (300, 40, 105, 0)
    assert e.source == "Brazil CONAB"
    e = cal.at(-23.25, -51.25)                                    # centre: no data, neighbour has
    assert e.distance_cells == 1 and (e.cell_lat, e.cell_lon) == (-22.75, -50.75)
    assert cal.at(-23.75, -51.75, max_distance=1) is None         # 2 cells away
    t = cal.table(pd.DataFrame({"id": ["a", "b"], "lat": [-22.75, -23.75], "lon": [-50.75, -51.75]}),
                  max_distance=1)
    assert t.loc[0, "planting_doy"] == 300 and np.isnan(t.loc[1, "planting_doy"])


def test_sowing_window_wraps():
    assert sowing_window(304, 30) == (274, 334)
    assert sowing_window(10, 30) == (345, 40)
    assert sowing_window(350, 30) == (320, 15)


def test_sowing_dates():
    d = sowing_dates(304, [2019, 2020], [-10, 25])
    assert d == [date(2019, 10, 21), date(2020, 11, 24)]           # 2020 is a leap year
    with pytest.raises(ValueError):
        sowing_dates(304, [2019], [0, 1])
