"""DSSAT soil profiles (``SOIL.SOL``)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ._fmt import num

#: Layer columns written to SOIL.SOL (DSSAT names, lowercase), width 6 each.
#: slb depth to layer bottom (cm); slll/sdul/ssat water at lower limit, drained upper
#: limit and saturation (cm³/cm³); srgf root growth factor (0-1); ssks saturated
#: hydraulic conductivity (cm/h); sbdm bulk density (g/cm³); sloc organic carbon (%);
#: slcl clay (%); slsi silt (%); slcf coarse fraction (%); slni total N (%);
#: slhw pH in water; scec CEC (cmol/kg).
LAYER_COLUMNS = ["slb", "slmh", "slll", "sdul", "ssat", "srgf", "ssks", "sbdm", "sloc",
                 "slcl", "slsi", "slcf", "slni", "slhw", "slhb", "scec", "sadc"]
_DECIMALS = {"slb": 0, "slll": 3, "sdul": 3, "ssat": 3, "srgf": 3, "ssks": 2, "sbdm": 2,
             "sloc": 2, "slcl": 1, "slsi": 1, "slcf": 1, "slni": 3, "slhw": 1, "slhb": 1,
             "scec": 1, "sadc": 1}
REQUIRED = ("slb", "slll", "sdul", "ssat", "sbdm", "sloc")


@dataclass
class SoilProfile:
    """One soil profile. ``layers`` has one row per layer with :data:`LAYER_COLUMNS`
    (missing optional columns are written as -99)."""

    layers: pd.DataFrame
    texture: str = "-99"      # SLTX, up to 5 characters (e.g. "SICL")
    albedo: float = 0.13      # SALB
    slu1: float = 6.0         # evaporation limit (mm)
    sldr: float = 0.6         # drainage rate (1/d)
    slro: float = 73.0        # runoff curve number
    slnf: float = 1.0         # mineralization factor
    slpf: float = 1.0         # photosynthesis factor
    lat: float | None = None
    lon: float | None = None
    source: str = "cropemu"
    description: str = "-99"

    def __post_init__(self):
        missing = [c for c in REQUIRED if c not in self.layers]
        if missing:
            raise ValueError(f"soil layers lack columns {missing}")
        bad = self.layers.query("not (slll < sdul < ssat)")
        if len(bad):
            raise ValueError(f"layers must satisfy slll < sdul < ssat; violated at depths {bad.slb.tolist()}")

    @property
    def depth(self) -> float:
        return float(self.layers["slb"].max())

    def to_sol(self, soil_id: str) -> str:
        """Text block of this profile (without the ``*SOILS`` file header)."""
        if len(soil_id) != 10:
            raise ValueError("soil ID must have 10 characters")
        lines = [f"*{soil_id}  {self.source[:11]:<11s} {self.texture[:5]:<5s} {num(self.depth, 5, 0)} "
                 f"{self.description[:50]}",
                 "@SITE        COUNTRY          LAT     LONG SCS FAMILY",
                 f" {'-99':<11s} {'-99':<11s} {num(self.lat, 8, 3)} {num(self.lon, 8, 3)} -99",
                 "@ SCOM  SALB  SLU1  SLDR  SLRO  SLNF  SLPF  SMHB  SMPX  SMKE",
                 # Fortran (1X, A5, 6(1X, F5.0), 3(1X, A5))
                 "   -99" + "".join(" " + num(v, 5, d) for v, d in (
                     (self.albedo, 2), (self.slu1, 1), (self.sldr, 2), (self.slro, 1), (self.slnf, 2),
                     (self.slpf, 2))) + " IB001 IB001 IB001",
                 "@" + "".join(f"{c.upper():>6s}" for c in LAYER_COLUMNS)[1:]]
        for r in self.layers.to_dict("records"):
            # Fortran (1X, F5.0, 1X, A5, n(1X, F5.0)): every field is a space plus 5 characters
            cells = []
            for c in LAYER_COLUMNS:
                v = r.get(c)
                if c == "slmh":
                    cells.append(f" {('-99' if v is None else str(v))[:5]:>5s}")
                else:
                    cells.append(" " + num(v, 5, _DECIMALS[c]))
            lines.append("".join(cells))
        return "\n".join(lines) + "\n"


def write_sol(path, profiles: dict[str, SoilProfile]) -> None:
    """Write a SOIL.SOL file with several profiles keyed by 10-character soil ID."""
    blocks = ["*SOILS: cropemu", ""] + [p.to_sol(sid) for sid, p in profiles.items()]
    path.write_text("\n".join(blocks))
