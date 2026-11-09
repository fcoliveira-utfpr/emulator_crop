"""CROPGRO-Soybean cultivars from a continuous maturity group (MG).

**Provisional** (until the systematic review gives published coefficients): the
baseline coefficients come from the default cultivars of the program itself, one
per maturity group in ``SBGRO048.CUL`` (rows 990011-990013 and 990001-990010),
interpolated linearly in MG. Independent perturbations around that baseline are
then applied and every coefficient is clipped to the MINIMA/MAXIMA rows of the file.

MG scale: 000 = -2, 00 = -1, 0 = 0, then 1 ... 10.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..models.dssat.cultivar import COEFFICIENTS, CUL_FILE, Cultivar, read_cultivars

MG_ROWS = {-2: "990011", -1: "990012", 0: "990013", 1: "990001", 2: "990002", 3: "990003", 4: "990004",
           5: "990005", 6: "990006", 7: "990007", 8: "990008", 9: "990009", 10: "990010"}
MG_MIN, MG_MAX = -2.0, 10.0

#: Perturbations around the MG baseline: (kind, low, high); "add" in coefficient units, "mul" factors.
PERTURBATIONS = {"CSDL": ("add", -0.3, 0.3), "PPSEN": ("mul", 0.8, 1.2),
                 "EM-FL": ("mul", 0.85, 1.15), "FL-SH": ("mul", 0.85, 1.15), "FL-SD": ("mul", 0.85, 1.15),
                 "SD-PM": ("mul", 0.85, 1.15), "FL-LF": ("mul", 0.85, 1.15), "LFMAX": ("mul", 0.85, 1.15),
                 "SLAVR": ("mul", 0.85, 1.15), "SIZLF": ("mul", 0.85, 1.15), "WTPSD": ("mul", 0.85, 1.15),
                 "SFDUR": ("mul", 0.85, 1.15), "SDPDV": ("mul", 0.85, 1.15)}

#: Typical maturity group by absolute latitude (piecewise linear, provisional rule of thumb):
#: tropics ~8-9, 23° (Paraná, Brazil) ~6.5, 40° (US Corn Belt) ~3, 50° ~000.
_MG_BY_LAT = ((0.0, 9.0), (15.0, 8.5), (23.0, 6.5), (30.0, 5.5), (35.0, 4.5), (40.0, 3.0), (45.0, 1.0),
              (50.0, -1.5), (60.0, -2.0))


def mg_center(lat) -> np.ndarray:
    """Typical maturity group at a latitude (used to centre the sampled MG range)."""
    x, y = zip(*_MG_BY_LAT)
    return np.interp(np.abs(np.asarray(lat, float)), x, y)


class MGTable:
    """Default MG cultivars and coefficient limits of a DSSAT installation."""

    def __init__(self, dssat_home):
        table = read_cultivars(Path(dssat_home) / "Genotype" / CUL_FILE).set_index("id")
        self.rows = table.loc[list(MG_ROWS.values()), COEFFICIENTS].to_numpy(float)   # 13 x 18
        self.mgs = np.array(list(MG_ROWS), float)
        self.low = table.loc["999991", COEFFICIENTS].to_numpy(float)
        self.high = table.loc["999992", COEFFICIENTS].to_numpy(float)

    def baseline(self, mg: float) -> np.ndarray:
        mg = float(np.clip(mg, MG_MIN, MG_MAX))
        return np.array([np.interp(mg, self.mgs, self.rows[:, k]) for k in range(len(COEFFICIENTS))])


def ecotype(mg: float) -> str:
    """Ecotype of the nearest maturity group (SB0001 for MG <= 0)."""
    k = int(np.clip(round(mg), 0, 10))
    return "SB0001" if k == 0 else f"SB{k:02d}01"


def cultivar_from_mg(table: MGTable, cultivar_id: str, mg: float, u: dict[str, float] | None = None) -> Cultivar:
    """Cultivar for maturity group ``mg``; ``u`` maps coefficients of :data:`PERTURBATIONS`
    to numbers in [0, 1] (e.g. Latin hypercube) that place them in their range."""
    coef = dict(zip(COEFFICIENTS, table.baseline(mg)))
    low, high = dict(zip(COEFFICIENTS, table.low)), dict(zip(COEFFICIENTS, table.high))
    for name, x in (u or {}).items():
        kind, lo, hi = PERTURBATIONS[name]
        v = lo + float(x) * (hi - lo)
        value = coef[name] + v if kind == "add" else coef[name] * v
        coef[name] = float(np.clip(value, low[name], high[name]))   # perturbed: within MINIMA/MAXIMA
    return Cultivar(cultivar_id, ecotype(mg), coef, name=f"cropemu MG{mg:.2f}")


def cultivar_table(cultivars: list[Cultivar]) -> pd.DataFrame:
    return pd.DataFrame([{"cultivar": c.id, "ecotype": c.ecotype, **c.coefficients} for c in cultivars])
