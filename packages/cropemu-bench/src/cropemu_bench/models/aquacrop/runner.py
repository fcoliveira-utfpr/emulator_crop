"""Batch execution of the official AquaCrop v7 stand-alone executable.

Each season is a single-season project (PRO) with its own climate files (so
climate perturbations are per season), crop file (cultivar), soil and initial
water. Seasons are run in chunks, one folder and one AquaCrop process per chunk.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..base import CropModel, SimulationResult
from .crop import CropFile
from .files import AquaSoil, write_climate, write_co2, write_net_irrigation, write_pro, write_sw0
from .outputs import crop_period_summary, read_daily, read_season

#: Daily output groups: 1 water balance, 2 crop development and production,
#: 3 soil water in profile and root zone, 7 climate.
DAILY_GROUPS = (1, 2, 3, 7)


class AquaCropError(RuntimeError):
    pass


@dataclass
class Season:
    """One AquaCrop season.

    ``weather``: daily ``tmin``, ``tmax``, ``rain``, ``eto`` from ``start`` (perturbations already
    applied). AquaCrop converts the GDD cycle to calendar days with this record, so it should
    extend past the end of the cycle; seasons whose cycle is not completed within it are
    not run (``error`` set, ``matured`` False). ``co2``: constant ppm, or None for the Mauna Loa series.
    ``irrigated``: net irrigation requirement (no water stress).
    """

    weather: pd.DataFrame          # from ``start``; may extend past ``end`` (GDD -> calendar days)
    soil: AquaSoil
    crop: CropFile
    sowing: object
    start: object
    end: object
    co2: float | None = None
    irrigated: bool = False
    initial_water: float = 0.5


def cycle_reachable(s: Season) -> bool:
    """Whether the GDD to maturity of the crop accumulate within the climate record."""
    from ...design.aquacrop import gdd

    w = s.weather.loc[pd.Timestamp(s.sowing):]
    g = gdd(w["tmax"].to_numpy(float), w["tmin"].to_numpy(float), s.crop["tbase"], s.crop["tupper"])
    return float(g.sum()) >= s.crop["gdd_maturity"]


class AquaCrop(CropModel):
    """AquaCrop v7 (FAO) from its executable.

    Parameters
    ----------
    executable
        Path to ``aquacrop``. Default: environment variable ``CROPEMU_AQUACROP_EXE``.
        Its ``SIMUL`` folder (with ``MaunaLoa.CO2``) must be next to it.
    crop_dir
        Folder with the FAO crop files (``DATA`` of the AquaCrop distribution).
        Default: ``CROPEMU_AQUACROP_DATA``.
    """

    name = "aquacrop"

    def __init__(self, executable=None, crop_dir=None, workdir=None):
        executable = executable or os.environ.get("CROPEMU_AQUACROP_EXE")
        crop_dir = crop_dir or os.environ.get("CROPEMU_AQUACROP_DATA")
        if not executable:
            raise ValueError("give executable or set CROPEMU_AQUACROP_EXE")
        self.executable = Path(executable).resolve()
        if not self.executable.is_file():
            raise FileNotFoundError(self.executable)
        self.simul = self.executable.parent / "SIMUL"
        if not (self.simul / "MaunaLoa.CO2").is_file():
            raise FileNotFoundError(f"MaunaLoa.CO2 not found in {self.simul}")
        self.crop_dir = Path(crop_dir).resolve() if crop_dir else None
        self.workdir = workdir

    def crop(self, name: str = "SoybeanGDD") -> CropFile:
        """A crop of the FAO database (e.g. ``SoybeanGDD``, ``MaizeGDD``)."""
        if self.crop_dir is None:
            raise ValueError("give crop_dir or set CROPEMU_AQUACROP_DATA")
        return CropFile.read(self.crop_dir / f"{name}.CRO")

    def _prepare(self, folder: Path) -> None:
        for sub in ("LIST", "DATA", "SIMUL", "OUTP", "PARAM"):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy(self.simul / "MaunaLoa.CO2", folder / "SIMUL" / "MaunaLoa.CO2")
        (folder / "SIMUL" / "DailyResults.SIM").write_text("".join(f" {g} :\n" for g in DAILY_GROUPS))
        (folder / "SIMUL" / "ParticularResults.SIM").write_text("")
        (folder / "SIMUL" / "AggregationResults.SIM").write_text("0 : seasonal results only\n")
        write_net_irrigation(folder / "DATA" / "INET.IRR")

    def _run_chunk(self, folder: Path, seasons: list[Season], offset: int, daily: bool) -> tuple:
        self._prepare(folder)
        names, skipped = [], {}
        for k, s in enumerate(seasons):
            n = f"S{offset + k}"
            if not cycle_reachable(s):
                skipped[n] = "crop cycle (GDD) not completed within the climate record"
                names.append(n)
                continue
            co2, co2_dir = "MaunaLoa.CO2", "'./SIMUL/'"
            if s.co2 is not None and pd.notna(s.co2):
                co2, co2_dir = f"{n}.CO2", "'./DATA/'"
                write_co2(folder / "DATA" / co2, float(s.co2))
            w = s.weather.loc[pd.Timestamp(s.start):]
            cli = write_climate(folder / "DATA", n, w, co2_file=co2)
            s.crop.write(folder / "DATA" / f"{n}.CRO")
            (folder / "DATA" / f"{n}.SOL").write_text(s.soil.to_sol())
            write_sw0(folder / "DATA" / f"{n}.SW0", s.soil, s.initial_water)
            write_pro(folder / "LIST" / f"{n}.PRO", s.start, s.end, s.sowing, cli, f"{n}.CRO", f"{n}.SOL",
                      co2=co2, co2_dir=co2_dir, irrigation="INET.IRR" if s.irrigated else None,
                      initial=f"{n}.SW0", title=n)
            names.append(n)
        (folder / "LIST" / "ListProjects.txt").write_text(
            "\n".join(f"{n}.PRO" for n in names if n not in skipped) + "\n")
        proc = subprocess.run([str(self.executable)], cwd=folder, capture_output=True, text=True)
        rows, days = [], []
        for k, n in enumerate(names):
            sp, dp = folder / "OUTP" / f"{n}PROseason.OUT", folder / "OUTP" / f"{n}PROday.OUT"
            if n in skipped:
                rows.append({"treatment": offset + k, "error": skipped[n], "matured": False})
                continue
            if not sp.exists():
                rows.append({"treatment": offset + k, "error": "no output"})
                continue
            season = read_season(sp)
            rec = {"treatment": offset + k, **season.iloc[0].drop(labels=["RunNr"], errors="ignore").to_dict()}
            if dp.exists():
                d = read_daily(dp)
                rec.update(crop_period_summary(d))
                if daily:
                    d.insert(0, "treatment", offset + k)
                    days.append(d)
            rows.append(rec)
        if len(skipped) < len(names) and not any("error" not in r for r in rows):
            raise AquaCropError(f"AquaCrop produced no output in {folder}:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
        return rows, days

    def simulate(self, seasons: list[Season], n_jobs: int = 4, chunk_size: int = 100, daily: bool = False,
                 keep: bool = False) -> SimulationResult:
        root = Path(tempfile.mkdtemp(prefix="cropemu_aquacrop_", dir=self.workdir))
        chunks = [(k, seasons[k:k + chunk_size]) for k in range(0, len(seasons), chunk_size)]
        try:
            with ThreadPoolExecutor(max_workers=n_jobs) as ex:
                res = list(ex.map(lambda c: self._run_chunk(root / f"c{c[0]:07d}", c[1], c[0], daily), chunks))
        finally:
            if not keep:
                shutil.rmtree(root, ignore_errors=True)
        summary = pd.DataFrame([r for rows, _ in res for r in rows])
        summary.insert(1, "season", 0)
        days = [d for _, dd in res for d in dd]
        out = {"day": pd.concat(days, ignore_index=True)} if days else {}
        return SimulationResult(summary=summary, daily=out)
