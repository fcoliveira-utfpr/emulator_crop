"""CROPGRO-Soybean cultivar files (``SBGRO048.CUL``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ._fmt import num

#: Cultivar coefficients of CROPGRO-Soybean, in file order.
COEFFICIENTS = ["CSDL", "PPSEN", "EM-FL", "FL-SH", "FL-SD", "SD-PM", "FL-LF", "LFMAX", "SLAVR",
                "SIZLF", "XFRT", "WTPSD", "SFDUR", "SDPDV", "PODUR", "THRSH", "SDPRO", "SDLIP"]
CUL_FILE = "SBGRO048.CUL"


@dataclass
class Cultivar:
    """A cultivar: 6-character ID, ecotype and the 18 coefficients."""

    id: str
    ecotype: str
    coefficients: dict[str, float]
    name: str = "cropemu"

    def __post_init__(self):
        if len(self.id) != 6:
            raise ValueError("cultivar ID must have 6 characters")
        missing = [c for c in COEFFICIENTS if c not in self.coefficients]
        if missing:
            raise ValueError(f"cultivar {self.id} lacks coefficients {missing}")

    def to_line(self) -> str:
        return (f"{self.id} {self.name[:16]:<16s}     . {self.ecotype:<6s}"
                + "".join(" " + num(self.coefficients[c], 5, 3) for c in COEFFICIENTS))

    def with_(self, **coefficients) -> "Cultivar":
        """Copy with some coefficients replaced (keys may use '_' for '-', e.g. EM_FL)."""
        new = dict(self.coefficients)
        new.update({k.replace("_", "-"): v for k, v in coefficients.items()})
        return Cultivar(self.id, self.ecotype, new, self.name)


def read_cultivars(path: Path) -> pd.DataFrame:
    """Cultivars of a .CUL file: columns ``id``, ``name``, ``ecotype`` and the coefficients."""
    rows = []
    for line in Path(path).read_text(encoding="latin-1").splitlines():
        if not line.strip() or line[0] in "!@*$":
            continue
        values = line[36:].split()
        if len(values) < len(COEFFICIENTS):
            continue
        rows.append({"id": line[:6], "name": line[7:23].strip(), "ecotype": line[30:36].strip(),
                     **{c: float(v) for c, v in zip(COEFFICIENTS, values)}})
    return pd.DataFrame(rows)


def default_cultivar(dssat_home: Path, cultivar_id: str) -> Cultivar:
    """A cultivar from the default SBGRO048.CUL of a DSSAT installation."""
    table = read_cultivars(Path(dssat_home) / "Genotype" / CUL_FILE).set_index("id")
    r = table.loc[cultivar_id]
    return Cultivar(cultivar_id, r["ecotype"], {c: float(r[c]) for c in COEFFICIENTS}, r["name"])


def write_cul(path: Path, base: Path, cultivars: list[Cultivar]) -> None:
    """Write a .CUL file: the default file ``base`` followed by ``cultivars``.

    Custom IDs must not collide with IDs already in ``base``.
    """
    text = Path(base).read_text(encoding="latin-1").rstrip("\n")
    existing = set(read_cultivars(base)["id"])
    clash = [c.id for c in cultivars if c.id in existing]
    if clash:
        raise ValueError(f"cultivar IDs already in {base.name}: {clash}")
    Path(path).write_text(text + "\n" + "\n".join(c.to_line() for c in cultivars) + "\n",
                          encoding="latin-1")
