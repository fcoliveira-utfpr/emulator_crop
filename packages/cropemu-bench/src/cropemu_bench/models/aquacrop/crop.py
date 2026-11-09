"""AquaCrop crop files (.CRO): read, change named parameters, write.

A CRO file is a description line followed by one ``value : comment`` per line,
in a fixed order. Parameters are found by a unique piece of their comment, so
the files of the FAO crop database are used as they are.
"""

from __future__ import annotations

import copy
from pathlib import Path

#: name -> piece of the comment (lower case) identifying the line (first match in file order).
PARAMETERS = {
    "tbase": "base temperature",
    "tupper": "upper temperature",
    "gdd_cycle": "total length of crop cycle in growing degree-days",
    "p_exp_upper": "(p-exp) - upper threshold",
    "p_exp_lower": "(p-exp) - lower threshold",
    "p_sto": "stomatal control (p - sto)",
    "p_sen": "canopy senescence (p - sen)",
    "p_pol": "pollination (p - pol)",
    "t_cold_pol": "minimum air temperature below which pollination",
    "t_heat_pol": "maximum air temperature above which pollination",
    "kctr": "(kctr,x)",
    "zmin": "minimum effective rooting depth (m)",
    "zmax": "maximum effective rooting depth",
    "plants": "number of plants per hectare",
    "ccx": "maximum canopy cover (ccx)",
    "wp": "(wp*)",
    "wp_yield": "during yield formation (as % wp*)",
    "hio": "reference harvest index",
    "gdd_emergence": "gddays: from sowing to emergence",
    "gdd_maxroot": "gddays: from sowing to maximum rooting depth",
    "gdd_senescence": "gddays: from sowing to start senescence",
    "gdd_maturity": "gddays: from sowing to maturity",
    "gdd_flowering": "gddays: from sowing to flowering",
    "gdd_flowering_length": "length of the flowering stage (growing degree days)",
    "cgc_gdd": "cgc for ggdays",
    "cdc_gdd": "cdc for ggdays",
    "gdd_hi": "gddays: building-up of harvest index",
}
#: GDD durations scaled together by the cycle factor (emergence is kept).
CYCLE_PARAMETERS = ("gdd_maxroot", "gdd_senescence", "gdd_maturity", "gdd_flowering",
                    "gdd_flowering_length", "gdd_hi")


class CropFile:
    def __init__(self, description: str, lines: list):
        self.description = description
        self.lines = lines                     # [value text, rest of the line incl. ':' comment]
        self._index = {}
        for name, piece in PARAMETERS.items():
            for i, (_, rest) in enumerate(lines):
                if piece in rest.lower():
                    self._index[name] = i
                    break
            else:
                raise KeyError(f"crop parameter {name!r} ({piece!r}) not in the file")

    @classmethod
    def read(cls, path) -> "CropFile":
        raw = Path(path).read_text(encoding="latin-1").splitlines()
        lines = []
        for line in raw[1:]:
            s = line.strip()
            if not s:
                continue
            value, _, rest = s.partition(" ")
            lines.append([value, rest])
        return cls(raw[0].rstrip(), lines)

    def __getitem__(self, name: str) -> float:
        return float(self.lines[self._index[name]][0])

    def __setitem__(self, name: str, value: float) -> None:
        i = self._index[name]
        old = self.lines[i][0]
        if "." in old:
            decimals = max(len(old.split(".")[1]), 6 if abs(value) < 0.1 else 0)
            self.lines[i][0] = f"{value:.{decimals}f}"
        else:
            self.lines[i][0] = str(int(round(value)))

    def copy(self) -> "CropFile":
        return copy.deepcopy(self)

    def scale_cycle(self, factor: float) -> None:
        """Scale every GDD duration after emergence (cycle length, the 'maturity group').

        Canopy growth and decline coefficients are divided by the factor, as the AquaCrop
        interface does when the cycle is changed: the canopy keeps its shape in the new cycle.
        """
        for name in CYCLE_PARAMETERS:
            self[name] = self[name] * factor
        self["gdd_cycle"] = self["gdd_maturity"]
        for name in ("cgc_gdd", "cdc_gdd"):
            self[name] = self[name] / factor

    def write(self, path, description: str | None = None) -> None:
        body = "\n".join(f"     {v:<10s}{rest}" for v, rest in self.lines)
        Path(path).write_text((description or self.description) + "\n" + body + "\n", encoding="latin-1")
