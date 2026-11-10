"""Loading and running an exported emulator (ONNX graph + card).

>>> cropemu.available()                                   # emulators shipped with the package
>>> emu = cropemu.load("dssat-soybean-v1")                 # or a folder with card.json and model.onnx
>>> res = emu.predict(weather, lat=-24.0, elev=500, soil=profile, sowing="2023-10-15",
...                   cultivar=emu.cultivar(mg=6.2))
>>> res.outputs, res.out_of_domain, res.rare_inputs, res.levels
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import units
from .features import WeatherSeries, co2_at, gdd, season_inputs, soil_features
from .soil.ptf import hydraulics

#: Folder of the emulators shipped with the package.
ZOO = Path(__file__).parent / "zoo"

#: Days of weather needed after sowing for the input windows (the thermal-time inputs may need more).
WEATHER_DAYS_AFTER = 130


@dataclass
class Prediction:
    """``outputs``: one row per season; ``out_of_domain``: per season, the inputs outside the
    range of the training data (or missing); ``rare_inputs``: the inputs outside its 0.5-99.5 %
    range (inside the domain, but where the emulator saw few seasons); ``levels``: acceptance level of every output
    ("recommended", "caution", "not recommended"; spatial block validation)."""

    outputs: pd.DataFrame
    inputs: pd.DataFrame
    out_of_domain: pd.Series
    rare_inputs: pd.Series
    levels: pd.Series

    def recommended(self, level: str = "caution") -> pd.DataFrame:
        """Outputs at ``level`` or better ("recommended" or "caution")."""
        ok = {"recommended": ["recommended"], "caution": ["recommended", "caution"]}[level]
        return self.outputs[[c for c in self.outputs if self.levels.get(c) in ok]]


class Emulator:
    """An exported emulator. Use :func:`load`."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.card = json.loads((self.folder / "card.json").read_text())
        self.inputs_ = list(self.card["inputs"])
        self.outputs_ = list(self.card["outputs"])
        self.cultivar_ = list(self.card.get("cultivar", []))
        self._session = None

    def __repr__(self):
        c = self.card
        return (f"Emulator({c.get('name')!r}: {c.get('model')}, {c.get('crop')}; {len(self.inputs_)} inputs, "
                f"{len(self.outputs_)} outputs)")

    @property
    def session(self):
        if self._session is None:
            import onnxruntime as ort

            self._session = ort.InferenceSession(str(self.folder / self.card["onnx"]["file"]),
                                                 providers=["CPUExecutionProvider"])
        return self._session

    @property
    def family(self) -> str:
        """``"dssat"`` or ``"aquacrop"`` (crop model emulated)."""
        return "aquacrop" if "aquacrop" in str(self.card.get("model", "")).lower() else "dssat"

    def describe(self) -> pd.DataFrame:
        """One row per output: description, unit, acceptance level and validation RMSE and R²."""
        u = units.table(self.family)
        a = self.card.get("acceptance", {})
        rows = [{"output": c, "description": u.get(c, ("", ""))[0], "unit": u.get(c, ("", ""))[1],
                 "level": a.get(c, {}).get("level", "unknown"), "rmse": a.get(c, {}).get("rmse", np.nan),
                 "r2": a.get(c, {}).get("r2", np.nan)} for c in self.outputs_ + list(self.card.get("derived", {}))]
        return pd.DataFrame(rows).set_index("output")

    def typical_mg(self, lat: float) -> float:
        """Typical soybean maturity group at a latitude (the centre of the training design)."""
        x, y = zip(*self.card["mg_by_lat"])
        return float(np.interp(abs(lat), x, y))

    def cultivar(self, mg: float | None = None, lat: float | None = None, weather=None, sowing=None,
                 cycle_days: int | None = None, **values) -> dict:
        """A typical cultivar (the parameters in ``card["cultivar"]``); ``values`` override any of them.

        DSSAT: the default coefficients of maturity group ``mg`` (or the typical MG of ``lat``).
        AquaCrop: the middle of the training range of every crop parameter. The cycle length
        ``gdd_maturity`` (growing degrees from sowing to maturity, Tbase 5 °C, Tupper 30 °C) is
        given, or computed from ``weather`` as the mean over the years of the ``cycle_days`` days
        after the day of year of ``sowing``; with ``mg`` and ``lat``, it is scaled by the cycle
        factor of the training design (+12.5 % per MG above the typical MG of the latitude, ±2 MG).
        """
        if self.family == "dssat":
            if mg is None:
                if lat is None:
                    raise ValueError("give mg or lat")
                mg = self.typical_mg(lat)
            t = self.card["cultivar_by_mg"]
            out = {"mg": float(mg), **{k: float(np.interp(mg, t["mg"], t[k])) for k in t if k != "mg"}}
        else:
            out = dict(self.card["cultivar_defaults"])
            if mg is not None and lat is not None:
                out["cycle_factor"] = 1 + 0.125 * float(np.clip(mg - self.typical_mg(lat), -2, 2))
            if "gdd_maturity" not in values:
                if weather is None or sowing is None or cycle_days is None:
                    raise ValueError("AquaCrop: give gdd_maturity, or weather, sowing and cycle_days")
                out["gdd_maturity"] = season_gdd(weather, sowing, cycle_days) * out["cycle_factor"]
        out.update(values)
        missing = [k for k in self.cultivar_ if k not in out]
        if missing:
            raise KeyError(f"missing cultivar parameters: {missing}")
        return {k: out[k] for k in self.cultivar_}

    @property
    def levels(self) -> pd.Series:
        a = self.card.get("acceptance", {})
        names = self.outputs_ + list(self.card.get("derived", {}))
        return pd.Series({c: a.get(c, {}).get("level", "unknown") for c in names}, name="level")

    def domain(self, X: pd.DataFrame, rare: bool = False) -> pd.Series:
        """Per row, the inputs outside the training range (min-max), or, with ``rare``, outside
        its 0.5-99.5 % range."""
        d = self.card["domain"]
        lo, hi = ("q005", "q995") if rare else ("min", "max")
        lo = np.array([d[c][lo] for c in self.inputs_])
        hi = np.array([d[c][hi] for c in self.inputs_])
        a = X[self.inputs_].to_numpy(float)
        bad = (a < lo) | (a > hi) | ~np.isfinite(a)
        names = np.array(self.inputs_)
        return pd.Series([list(names[b]) for b in bad], index=X.index, name="rare_inputs" if rare else "out_of_domain")

    def predict_inputs(self, X: pd.DataFrame) -> Prediction:
        """Predict from a table of inputs (columns: :attr:`inputs_`)."""
        missing = [c for c in self.inputs_ if c not in X]
        if missing:
            raise KeyError(f"missing inputs: {missing}")
        a = X[self.inputs_].to_numpy("float32")
        ok = np.isfinite(a).all(axis=1)
        out = np.full((len(X), len(self.outputs_)), np.nan)
        if ok.any():
            o = self.card["onnx"]
            out[ok] = self.session.run([o["output"]], {o["input"]: a[ok]})[0]
        P = pd.DataFrame(out, index=X.index, columns=self.outputs_)
        # ratios computed from predicted outputs: name -> [numerator, denominator, factor, floor]
        for name, (num, den, f, floor) in self.card.get("derived", {}).items():
            P[name] = f * P[num].clip(lower=0) / P[den].clip(lower=floor)
        return Prediction(P, X[self.inputs_], self.domain(X), self.domain(X, rare=True), self.levels)

    def inputs(self, weather, lat: float, soil, sowing, cultivar: dict, elev: float | None = None,
               irrigated: bool = False, co2: float | None = None, dt: float = 0.0,
               rain_factor: float = 1.0) -> pd.DataFrame:
        """Inputs of the seasons sown on ``sowing`` (a date or a list of dates).

        ``weather``: daily table (``cropemu.weather.fetch`` columns, filled) covering 30 days
        before to at least 130 days after each sowing; ``soil``: standard profile (e.g.
        ``cropemu.soil.soilgrids.fetch``; the water retention is computed with the method used in
        training, ``card["hydraulics"]``, unless it already has ``ll``/``dul``) or the dict of
        :func:`cropemu.features.soil_features`;
        ``cultivar``: the parameters in ``card["cultivar"]`` (see :meth:`cultivar`); ``irrigated``:
        no water stress; ``co2``: ppm (default: Mauna Loa ~60 days after sowing, as in training).
        Climate scenarios as in training: ``dt`` °C added to Tmax and Tmin and rain multiplied by
        ``rain_factor`` (training ranges: -1 to +4 °C, 0.7 to 1.3; CO2 350-800 ppm).
        """
        lost = [k for k in self.cultivar_ if k not in cultivar]
        if lost:
            raise KeyError(f"missing cultivar parameters: {lost}")
        w = weather if isinstance(weather, WeatherSeries) else WeatherSeries(weather, lat, elev)
        if not isinstance(soil, dict) and not {"ll", "dul"} <= set(soil):
            soil = hydraulics(soil, method=self.card.get("hydraulics", "saxton_rawls"), lat=lat)
        s = soil if isinstance(soil, dict) else soil_features(soil)
        dates = [sowing] if isinstance(sowing, (str, pd.Timestamp)) or not hasattr(sowing, "__iter__") else sowing
        rows = []
        for d in dates:
            d = pd.Timestamp(d)
            c = co2_at(d + pd.Timedelta(days=60)) if co2 is None else co2
            rows.append(season_inputs(w, s, d, {k: cultivar[k] for k in self.cultivar_}, irrigated=irrigated, co2=c,
                                      dt=dt, rain_factor=rain_factor, water_balance=self.card.get("water_balance", True),
                                      initial_water=self.card.get("initial_water", 0.5),
                                      thermal=self.card.get("thermal")))
        return pd.DataFrame(rows, index=pd.DatetimeIndex(dates, name="sowing"))

    def predict(self, weather, lat: float, soil, sowing, cultivar: dict, elev: float | None = None,
                irrigated: bool = False, co2: float | None = None, dt: float = 0.0,
                rain_factor: float = 1.0) -> Prediction:
        """Predict the outputs of the seasons sown on ``sowing`` (see :meth:`inputs`)."""
        return self.predict_inputs(self.inputs(weather, lat, soil, sowing, cultivar, elev, irrigated, co2,
                                               dt, rain_factor))


def season_gdd(weather, sowing, days: int, tbase: float = 5.0, tupper: float = 30.0) -> float:
    """Mean growing degrees (AquaCrop method 3) of the ``days`` days after the day of year of
    ``sowing``, over the complete years of ``weather``."""
    g = pd.Series(gdd(weather["tmax"].to_numpy(float), weather["tmin"].to_numpy(float), tbase, tupper),
                  index=pd.DatetimeIndex(weather.index))
    doy = pd.Timestamp(sowing).dayofyear
    sums = []
    for y in range(g.index[0].year, g.index[-1].year + 1):
        s = pd.Timestamp(y, 1, 1) + pd.Timedelta(days=doy - 1)
        e = s + pd.Timedelta(days=int(days))
        if s >= g.index[0] and e <= g.index[-1]:
            sums.append(g.loc[s:e].sum())
    if not sums:
        raise ValueError("weather does not cover any complete season")
    return float(np.mean(sums))


def available() -> list[str]:
    """Names of the emulators shipped with the package."""
    return sorted(p.name for p in ZOO.iterdir() if (p / "card.json").exists()) if ZOO.exists() else []


def load(name_or_path) -> Emulator:
    """Load an emulator: a name of :func:`available` or a folder with ``card.json`` and ``model.onnx``."""
    p = Path(name_or_path)
    if (p / "card.json").exists():
        return Emulator(p)
    if (ZOO / str(name_or_path) / "card.json").exists():
        return Emulator(ZOO / str(name_or_path))
    raise FileNotFoundError(f"no emulator {name_or_path!r}; shipped: {available()}")
