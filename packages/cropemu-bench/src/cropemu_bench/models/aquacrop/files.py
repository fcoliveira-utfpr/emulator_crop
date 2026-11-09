"""AquaCrop v7 input files: climate (CLI, Tnx, ETo, PLU, CO2), soil (SOL), initial water (SW0),
net irrigation (IRR) and single-season projects (PRO).

Formats follow the AquaCrop 7.3 reference manual and the Fortran readers
(``project_input.f90``, ``global.f90``); every value is read list-directed, so
only the line order matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "7.3"
#: AquaCrop day number 1 = 1 January 1901.
DAY_ZERO = date(1900, 12, 31)
MAX_HORIZONS = 5


def day_number(d) -> int:
    return (pd.Timestamp(d).date() - DAY_ZERO).days


def _series_header(title: str, start) -> str:
    s = pd.Timestamp(start)
    return (f"{title}\n     1  : Daily records (1=daily, 2=10-daily and 3=monthly data)\n"
            f"     {s.day}  : First day of record (1, 11 or 21 for 10-day or 1 for months)\n"
            f"     {s.month}  : First month of record\n  {s.year}  : First year of record (1901 if not linked to a specific year)\n\n")


def write_climate(folder: Path, name: str, weather: pd.DataFrame, co2_file: str = "MaunaLoa.CO2",
                  title: str = "cropemu") -> str:
    """Write ``name``.CLI/.Tnx/.ETo/.PLU from a daily table with ``tmin``, ``tmax``, ``eto``, ``rain``
    (index: consecutive dates). Returns the CLI file name."""
    folder = Path(folder)
    start = weather.index[0]
    with open(folder / f"{name}.Tnx", "w") as f:
        f.write(_series_header(title, start) + "  Tmin (C)   TMax (C)\n========================\n")
        np.savetxt(f, weather[["tmin", "tmax"]].to_numpy(float), fmt="%.1f", delimiter="\t")
    for ext, col, head in (("ETo", "eto", "  Average ETo (mm/day)"), ("PLU", "rain", "  Total Rain (mm)")):
        with open(folder / f"{name}.{ext}", "w") as f:
            f.write(_series_header(title, start) + head + "\n=======================\n")
            np.savetxt(f, weather[col].to_numpy(float), fmt="%.1f")
    (folder / f"{name}.CLI").write_text(f"{title}\n {VERSION}  : AquaCrop Version (January 2026)\n"
                                        f"{name}.Tnx\n{name}.ETo\n{name}.PLU\n{co2_file}\n")
    return f"{name}.CLI"


def write_co2(path: Path, ppm: float) -> None:
    """A CO2 file with a constant concentration (climate perturbation)."""
    lines = [f"Constant CO2 {ppm:.1f} ppm (cropemu)", "Year     CO2 (ppm by volume)", "============================"]
    lines += [f"  {y}  {ppm:.2f}" for y in (1902, 2099)]
    Path(path).write_text("\n".join(lines) + "\n")


def curve_number(ksat_mm_d: float) -> int:
    """Default CN from the saturated conductivity of the top horizon (``DetermineCN_default``)."""
    if ksat_mm_d > 864:
        return 46
    if ksat_mm_d >= 347:
        return 61
    if ksat_mm_d >= 36:
        return 72
    return 77


def readily_evaporable_water(fc: float, wp: float) -> int:
    """REW (mm) of the AquaCrop soil defaults: 0.4 (FC - WP/2), vol% (matches the 13 FAO soils)."""
    return int(np.clip(round(0.4 * (fc - wp / 2)), 0, 15))


def soil_class(sat: float, fc: float, wp: float, ksat: float) -> int:
    """AquaCrop soil class for capillary rise (``NumberSoilClass``): 1 sandy, 2 loamy,
    3 sandy clayey, 4 silty clayey."""
    if sat <= 55:
        if wp >= 20:
            return 4 if (sat >= 49 and fc >= 40) else 3
        if fc < 23:
            return 1
        if wp > 16 and ksat < 100:
            return 3
        if wp < 6 and fc < 28 and ksat > 750:
            return 1
        return 2
    return 4


def capillary_rise_parameters(cls: int, ksat: float) -> tuple[float, float]:
    """CRa, CRb (``DetermineParametersCR``)."""
    if ksat <= 0:
        return -9.0, -9.0
    if cls == 1:
        return -0.3112 - ksat / 1e5, -1.4936 + 0.2416 * np.log(ksat)
    if cls == 2:
        return -0.4986 + 9 * ksat / 1e5, -2.1320 + 0.4778 * np.log(ksat)
    if cls == 3:
        return -0.5677 - 4 * ksat / 1e5, -3.7189 + 0.5922 * np.log(ksat)
    return -0.6366 + 8 * ksat / 1e4, -1.9165 + 0.7063 * np.log(ksat)


@dataclass
class AquaSoil:
    """Soil profile in AquaCrop units: thickness m; sat, fc, wp vol%; ksat mm/d; gravel mass %."""

    thickness: list
    sat: list
    fc: list
    wp: list
    ksat: list
    gravel: list = field(default_factory=list)
    description: str = "cropemu soil"

    @classmethod
    def from_standard(cls, h: pd.DataFrame, description: str = "SoilGrids 2.0") -> "AquaSoil":
        """From a cropemu profile with hydraulics (``top``/``bottom`` cm, ``ll``/``dul``/``sat``
        cm³/cm³, ``ksat`` cm/h, optional ``cfvo`` vol % and ``bdod`` g/cm³). The two top
        layers are merged when there are more than 5 (AquaCrop's maximum)."""
        h = h.sort_values("top").reset_index(drop=True)
        groups = [[i] for i in range(len(h))]
        while len(groups) > MAX_HORIZONS:               # merge the top layers (thinnest in SoilGrids)
            groups = [groups[0] + groups[1]] + groups[2:]
        out = {k: [] for k in ("thickness", "sat", "fc", "wp", "ksat", "gravel")}
        for idx in groups:
            g = h.iloc[idx]
            w = (g["bottom"] - g["top"]).to_numpy(float)
            avg = lambda c: float(np.average(g[c].to_numpy(float), weights=w))
            sat, fc, wp = 100 * avg("sat"), 100 * avg("dul"), 100 * avg("ll")
            # harmonic mean of Ksat across merged layers (flow across layers in series)
            ks = float(w.sum() / np.sum(w / np.maximum(g["ksat"].to_numpy(float), 1e-6))) * 240  # cm/h -> mm/d
            gv = 0.0
            if "cfvo" in g and "bdod" in g and g["cfvo"].notna().all():
                v, bd = avg("cfvo") / 100, avg("bdod")
                gv = 100 * v * 2.65 / (v * 2.65 + (1 - v) * bd)    # volume -> mass fraction
            out["thickness"].append(w.sum() / 100)
            out["sat"].append(sat), out["fc"].append(fc), out["wp"].append(wp)
            out["ksat"].append(ks), out["gravel"].append(gv)
        return cls(**out, description=description)

    def to_sol(self) -> str:
        cn = curve_number(self.ksat[0])
        rew = readily_evaporable_water(self.fc[0], self.wp[0])
        lines = [self.description, f"        {VERSION}                 : AquaCrop Version (January 2026)",
                 f"{cn:9d}                   : CN (Curve Number)",
                 f"{rew:9d}                   : Readily evaporable water from top layer (mm)",
                 f"{len(self.thickness):9d}                   : number of soil horizons",
                 "       -9                   : variable no longer applicable",
                 "  Thickness  Sat   FC    WP     Ksat   Penetrability  Gravel  CRa       CRb           description",
                 "  ---(m)-   ----(vol %)-----  (mm/day)      (%)        (%)    -----------------------------------------"]
        gravel = self.gravel or [0.0] * len(self.thickness)
        for t, s, f, w, k, g in zip(self.thickness, self.sat, self.fc, self.wp, self.ksat, gravel):
            a, b = capillary_rise_parameters(soil_class(s, f, w, k), k)
            lines.append(f"{t:8.2f}{s:8.1f}{f:6.1f}{w:6.1f}{k:8.1f}{100:11d}{int(round(g)):10d}{a:14.6f}{b:10.6f}   layer")
        return "\n".join(lines) + "\n"

    def initial_water(self, fraction: float) -> list:
        """Water content (vol%) of each horizon at ``fraction`` of the available water."""
        return [w + fraction * (f - w) for f, w in zip(self.fc, self.wp)]


def write_sw0(path: Path, soil: AquaSoil, fraction: float) -> None:
    lines = ["cropemu initial soil water", f"     {VERSION}   : AquaCrop Version (January 2026)",
             "    -9.00  : initial canopy cover (%) at start of simulation period",
             "     0.000 : biomass (ton/ha) produced before the start of the simulation period",
             "    -9.00  : initial rooting depth (m) at start of simulation period",
             "     0.0   : water layer (mm) stored between soil bunds (if present)",
             "     0.00  : electrical conductivity (dS/m) of water layer stored between soil bunds (if present)",
             "     0     : soil water content specified for specific layers",
             f"     {len(soil.thickness)}     : number of layers considered", "",
             "Thickness layer (m)     Water content (vol%)     ECe(dS/m)",
             "=============================================================="]
    lines += [f"     {t:.2f}                    {w:.2f}                    0.00"
              for t, w in zip(soil.thickness, soil.initial_water(fraction))]
    Path(path).write_text("\n".join(lines) + "\n")


def write_net_irrigation(path: Path, depletion_raw: int = 0) -> None:
    """Net irrigation requirement: AquaCrop keeps the root zone above ``depletion_raw`` % of RAW
    (no water stress; the potential regime)."""
    Path(path).write_text(f"Net irrigation requirement (allowable depletion {depletion_raw} % RAW)\n"
                          f"   {VERSION}   : AquaCrop Version (January 2026)\n"
                          "   1     : Sprinkler irrigation\n 100     : Percentage of soil surface wetted by irrigation\n"
                          "   3     : Determination of Net Irrigation requirement\n"
                          f"  {depletion_raw}     : Allowable depletion of RAW (%)\n")


def _entry(info: str, name, directory="'./DATA/'") -> list:
    if name is None:
        return [info, "   (None)", "   (None)"]
    return [info, f"   {name}", f"   {directory}"]


def write_pro(path: Path, sim_start, sim_end, sowing, cli: str, crop: str, soil: str,
              co2: str = "MaunaLoa.CO2", co2_dir: str = "'./SIMUL/'", irrigation: str | None = None,
              initial: str | None = None, management: str | None = None, title: str = "cropemu") -> None:
    """A single-season project (PRO). Files are in ``./DATA/`` relative to the run folder."""
    stem = cli[:-4]
    d0, dn, ds = day_number(sim_start), day_number(sim_end), day_number(sowing)
    lines = [title, f"      {VERSION}  : AquaCrop Version (January 2026)",
             "      1         : Year number of cultivation (Seeding/planting year)",
             f"  {d0}         : First day of simulation period",
             f"  {dn}         : Last day of simulation period",
             f"  {ds}         : First day of cropping period",
             f"  {ds}         : Last day of cropping period (recomputed by AquaCrop from the crop cycle)"]
    lines += _entry("-- 1. Climate (CLI) file", cli)
    lines += _entry("   1.1 Temperature (Tnx or TMP) file", f"{stem}.Tnx")
    lines += _entry("   1.2 Reference ET (ETo) file", f"{stem}.ETo")
    lines += _entry("   1.3 Rain (PLU) file", f"{stem}.PLU")
    lines += _entry("   1.4 Atmospheric CO2 concentration (CO2) file", co2, co2_dir)
    lines += _entry("-- 2. Calendar (CAL) file", None)
    lines += _entry("-- 3. Crop (CRO) file", crop)
    lines += _entry("-- 4. Irrigation management (IRR) file", irrigation)
    lines += _entry("-- 5. Field management (MAN) file", management)
    lines += _entry("-- 6. Soil profile (SOL) file", soil)
    lines += _entry("-- 7. Groundwater table (GWT) file", None)
    lines += _entry("-- 8. Initial conditions (SW0) file", initial)
    lines += _entry("-- 9. Off-season conditions (OFF) file", None)
    lines += _entry("-- 10. Field data (OBS) file", None)
    Path(path).write_text("\n".join(lines) + "\n")
