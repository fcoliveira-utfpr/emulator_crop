"""Daily weather in the cropemu standard format.

Every daily weather table in cropemu is a ``pandas.DataFrame`` indexed by date
(daily, no gaps) with these columns and units:

========  ==========================================
srad      solar radiation, MJ/m²/d
tmax      maximum air temperature at 2 m, °C
tmin      minimum air temperature at 2 m, °C
rain      precipitation, mm/d
rhum      relative humidity at 2 m, %
wind      wind speed at 2 m, m/s
dewp      dew point temperature at 2 m, °C
========  ==========================================

``srad``, ``tmax``, ``tmin`` and ``rain`` are required; the others are optional.
Site information goes in ``df.attrs`` (``lat``, ``lon``, ``elev`` in m, ``source``).
"""

from .eto import eto_fao56
from .nasa_power import fetch, fetch_many
from .qc import check, fill_gaps

COLUMNS = ("srad", "tmax", "tmin", "rain", "rhum", "wind", "dewp")
REQUIRED = ("srad", "tmax", "tmin", "rain")

__all__ = ["COLUMNS", "REQUIRED", "eto_fao56", "fetch", "fetch_many", "check", "fill_gaps"]
