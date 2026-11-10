"""Loading and running an exported emulator (ONNX graph + card).

>>> emu = cropemu.load("path/to/dssat-soybean")            # folder with card.json and model.onnx
>>> res = emu.predict(weather, lat=-24.0, elev=500, soil=profile, sowing="2023-10-15",
...                   cultivar={"mg": 6.2, ...})
>>> res.outputs, res.out_of_domain, res.rare_inputs, res.levels
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .features import WeatherSeries, co2_at, season_inputs, soil_features
from .soil.ptf import hydraulics

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
               irrigated: bool = False, co2: float | None = None) -> pd.DataFrame:
        """Inputs of the seasons sown on ``sowing`` (a date or a list of dates).

        ``weather``: daily table (``cropemu.weather.fetch`` columns, filled) covering 30 days
        before to at least 130 days after each sowing; ``soil``: standard profile (e.g.
        ``cropemu.soil.soilgrids.fetch``; the water retention is computed with the method used in
        training, ``card["hydraulics"]``, unless it already has ``ll``/``dul``) or the dict of
        :func:`cropemu.features.soil_features`;
        ``cultivar``: the parameters in ``card["cultivar"]``; ``co2``: ppm (default: Mauna Loa
        ~60 days after sowing, as in training).
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
                                      water_balance=self.card.get("water_balance", True),
                                      initial_water=self.card.get("initial_water", 0.5),
                                      thermal=self.card.get("thermal")))
        return pd.DataFrame(rows, index=pd.DatetimeIndex(dates, name="sowing"))

    def predict(self, weather, lat: float, soil, sowing, cultivar: dict, elev: float | None = None,
                irrigated: bool = False, co2: float | None = None) -> Prediction:
        """Predict the outputs of the seasons sown on ``sowing`` (see :meth:`inputs`)."""
        return self.predict_inputs(self.inputs(weather, lat, soil, sowing, cultivar, elev, irrigated, co2))


def load(path) -> Emulator:
    """Load an exported emulator from a folder with ``card.json`` and ``model.onnx``."""
    return Emulator(path)
