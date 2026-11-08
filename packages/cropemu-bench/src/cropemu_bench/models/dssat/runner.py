"""Batch execution of the DSSAT CSM executable."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from ..base import CropModel, SimulationResult
from ._fmt import code
from .cultivar import CUL_FILE, Cultivar, write_cul
from .filex import MAX_TREATMENTS, Treatment, write_filex
from .outputs import read_daily, read_overview_stress, read_summary
from .soil import SoilProfile, write_sol
from .weather import Weather

FILEX = "CEMU0001.SBX"
PROFILE = "DSSATPRO.L48"
GENOTYPE_FILES = ("SBGRO048.ECO", "SBGRO048.SPE")
#: Output files that are not daily tables (season summaries, logs, text reports).
SEASON_FILES = {"Summary", "EnvSum", "OVERVIEW", "ERROR", "WARNING", "INFO", "RunList", "LUN", "Evaluate",
                "SWBalSum", "SoilWatBal", "SoilNiBal", "SoilCBal", "PlantNBal", "SoilPiBal", "OUTPUT"}


class DSSATError(RuntimeError):
    pass


class DSSAT(CropModel):
    """DSSAT CSM (CROPGRO-Soybean) run directly from its executable.

    Parameters
    ----------
    executable
        Path to ``dscsm048``. Default: environment variable ``CROPEMU_DSSAT_EXE``.
    dssat_home
        DSSAT ``Data`` directory (with ``Genotype``, ``StandardData``, ``Pest``...).
        Default: environment variable ``CROPEMU_DSSAT_HOME``.
    workdir
        Where run folders are created (default: a temporary directory).
    """

    name = "dssat"

    def __init__(self, executable=None, dssat_home=None, workdir=None):
        executable = executable or os.environ.get("CROPEMU_DSSAT_EXE")
        dssat_home = dssat_home or os.environ.get("CROPEMU_DSSAT_HOME")
        if not executable or not dssat_home:
            raise ValueError("give executable and dssat_home, or set CROPEMU_DSSAT_EXE and CROPEMU_DSSAT_HOME")
        self.executable = Path(executable).resolve()
        self.dssat_home = Path(dssat_home).resolve()
        if not self.executable.is_file():
            raise FileNotFoundError(self.executable)
        if not (self.dssat_home / "Genotype" / CUL_FILE).is_file():
            raise FileNotFoundError(f"{CUL_FILE} not found under {self.dssat_home / 'Genotype'}")
        if len(str(self.dssat_home)) > 90:
            raise ValueError("DSSAT truncates long paths: dssat_home must have at most 90 characters "
                             "(use a symbolic link with a shorter path)")
        self.workdir = Path(workdir) if workdir else None

    # ------------------------------------------------------------------ setup
    def _prepare_folder(self, folder: Path, cultivars: list[Cultivar]) -> None:
        (folder / "Weather").mkdir(parents=True, exist_ok=True)
        genotype = self.dssat_home / "Genotype"
        write_cul(folder / CUL_FILE, genotype / CUL_FILE, cultivars)
        for f in GENOTYPE_FILES:
            shutil.copy(genotype / f, folder / f)
        # DSSAT reads each DSSATPRO line as 80 characters: use paths relative to the run folder,
        # with links to the data folders of the installation.
        for link, target in (("pest", "Pest"), ("std", "StandardData")):
            os.symlink(self.dssat_home / target, folder / link)
        (folder / PROFILE).write_text(
            "WED    ./Weather\n"
            "MSB    ./ dscsm048 CRGRO048\n"
            "CRD    ./\n"
            "PSD    ./pest\n"
            "SLD    ./\n"
            "STD    ./std\n")

    def _run_chunk(self, folder: Path, treatments: list[Treatment], weather: dict[str, Weather],
                   insi: dict[str, str], soils: dict[str, SoilProfile], daily: tuple[str, ...],
                   overview: bool, retries: int) -> dict[str, pd.DataFrame]:
        wsta = {}
        for k in dict.fromkeys(t.weather for t in treatments):
            wsta[k] = weather[k].write(folder / "Weather", insi[k])
        write_sol(folder / "SOIL.SOL", {k: soils[k] for k in dict.fromkeys(t.soil for t in treatments)})
        write_filex(folder / FILEX, treatments, wsta, soils, daily=daily, overview=overview)
        expected = sum(t.seasons for t in treatments)

        for attempt in range(retries):
            for f in folder.glob("*.OUT"):
                f.unlink()
            proc = subprocess.run([str(self.executable), "A", FILEX], cwd=folder, capture_output=True,
                                  text=True, env={**os.environ, "DSSAT_HOME": f"{self.dssat_home}/"})
            summary_file = folder / "Summary.OUT"
            if summary_file.exists():
                summary = read_summary(summary_file)
                if len(summary) == expected:
                    break
        else:
            err = folder / "ERROR.OUT"
            msg = err.read_text(encoding="latin-1")[:1500] if err.exists() else proc.stdout[-1500:]
            raise DSSATError(f"DSSAT did not produce {expected} seasons in {folder}:\n{msg}")

        out = {"summary": summary}
        if (folder / "EnvSum.OUT").exists():
            env = read_summary(folder / "EnvSum.OUT")
            if len(env) == expected:
                out["envsum"] = env
        if overview and (folder / "OVERVIEW.OUT").exists():
            out["overview_stress"] = read_overview_stress(folder / "OVERVIEW.OUT")
        if daily:
            for f in sorted(folder.glob("*.OUT")):
                if f.stem in SEASON_FILES:
                    continue
                try:
                    table = read_daily(f)
                except Exception:          # noqa: BLE001 - files without daily tables are skipped
                    continue
                if len(table) and {"YEAR", "DOY"} <= set(table.columns):
                    out[f.stem] = table
        return out

    # ------------------------------------------------------------------ public
    def simulate(self, treatments: list[Treatment], weather: dict[str, Weather], soils: dict[str, SoilProfile],
                 cultivars: list[Cultivar] | None = None, daily: tuple[str, ...] = (), overview: bool = True,
                 n_jobs: int = 1, chunk_size: int = MAX_TREATMENTS, retries: int = 2,
                 keep_folders: bool = False) -> SimulationResult:
        """Simulate ``treatments`` and return all outputs.

        Parameters
        ----------
        weather
            Weather series keyed by the ``weather`` field of the treatments.
        soils
            Soil profiles keyed by 10-character soil ID (the ``soil`` field).
        cultivars
            Custom cultivars (e.g. sampled coefficients), added to the default
            SBGRO048.CUL. Treatments may also use any default cultivar ID.
        daily
            Daily output groups to write and read (see ``filex.OUTPUT_GROUPS``),
            e.g. ``("growth", "water")``. Empty: only season outputs.
        overview
            Also read the stress factors table of OVERVIEW.OUT.
        n_jobs
            Number of DSSAT processes running at once.
        """
        treatments = list(treatments)
        missing_w = {t.weather for t in treatments} - set(weather)
        missing_s = {t.soil for t in treatments} - set(soils)
        if missing_w or missing_s:
            raise KeyError(f"missing weather {missing_w or ''} soils {missing_s or ''}")
        insi = {k: code(i, 4) for i, k in enumerate(weather)}
        cultivars = list(cultivars or [])
        chunks = [treatments[i:i + chunk_size] for i in range(0, len(treatments), chunk_size)]
        offsets = [i for i in range(0, len(treatments), chunk_size)]

        base = Path(tempfile.mkdtemp(prefix="cropemu_dssat_", dir=self.workdir))
        try:
            def job(k):
                folder = base / f"chunk{k:06d}"
                self._prepare_folder(folder, cultivars)
                res = self._run_chunk(folder, chunks[k], weather, insi, soils, tuple(daily), overview, retries)
                if not keep_folders:
                    shutil.rmtree(folder, ignore_errors=True)
                return k, res

            if n_jobs == 1:
                results = [job(k) for k in range(len(chunks))]
            else:
                with ThreadPoolExecutor(max_workers=n_jobs) as ex:
                    results = list(ex.map(job, range(len(chunks))))
        finally:
            if not keep_folders:
                shutil.rmtree(base, ignore_errors=True)

        tables: dict[str, list[pd.DataFrame]] = {}
        for k, res in sorted(results, key=lambda kr: kr[0]):
            runmap = self._run_map(chunks[k], offsets[k])
            for name, df in res.items():
                tables.setdefault(name, []).append(runmap.merge(df, on="run").drop(columns="run"))
        merged = {n: pd.concat(v, ignore_index=True) for n, v in tables.items()}
        summary = merged.pop("summary")
        extra = {n: merged.pop(n) for n in list(merged) if n in ("overview_stress", "envsum")}
        return SimulationResult(summary=summary, daily=merged, extra=extra)

    @staticmethod
    def _run_map(treatments: list[Treatment], offset: int) -> pd.DataFrame:
        """DSSAT runs in file order: treatment 1 seasons 1..n, treatment 2, ..."""
        rows = [(offset + i, s) for i, t in enumerate(treatments) for s in range(t.seasons)]
        df = pd.DataFrame(rows, columns=["treatment", "season"])
        df.insert(0, "run", range(1, len(df) + 1))
        return df
