"""One emulator per group of outputs (e.g. a network for phenology dates and one for the rest).

A single network for every output shares its capacity among very different
targets; on dssat_v0 a network trained only on the phenology dates had ~25% lower
RMSE on flowering and maturity than the all-output network (plan, 4.7).
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .base import Emulator
from .mlp import MLPEmulator

#: Default groups: development dates (DSSAT and AquaCrop names); everything else.
PHENOLOGY = ("EDAT_dap", "ADAT_dap", "MDAT_dap", "HDAT_dap", "EMR_dap", "FLO_dap", "YLD_dap", "MAT_dap")
#: AquaCrop dates -> the thermal-time feature they follow (days to accumulate the stage GDD); with
#: these offsets the networks learn only the deviation of the date from the thermal-time estimate.
AQUACROP_OFFSETS = {"EMR_dap": "td_emergence", "FLO_dap": "td_flowering", "MAT_dap": "td_maturity"}


class GroupedEmulator(Emulator):
    """``groups`` maps a group name to its outputs; outputs in no group form ``"other"``.

    ``offsets`` maps an output to a feature: the members fit ``output - feature`` and the
    feature is added back to the prediction (outputs or features absent from the data are ignored).
    """

    name = "grouped"

    def __init__(self, factory=MLPEmulator, groups: dict | None = None, offsets: dict | None = None, **kw):
        self.factory, self.kw = factory, kw
        self.groups = {"phenology": PHENOLOGY} if groups is None else dict(groups)
        self.offsets = dict(offsets or {})

    def _shift(self, X: pd.DataFrame, Y: pd.DataFrame, sign: int) -> pd.DataFrame:
        Y = Y.copy()
        for c, f in self.offsets_.items():
            Y[c] = Y[c] + sign * X[f].to_numpy()
        return Y

    def fit(self, X: pd.DataFrame, Y: pd.DataFrame, groups=None) -> "GroupedEmulator":
        self.features_, self.targets_ = list(X.columns), list(Y.columns)
        self.offsets_ = {c: f for c, f in self.offsets.items() if c in Y and f in X}
        Y = self._shift(X, Y, -1)
        assigned = {c: g for g, cols in self.groups.items() for c in cols if c in Y}
        split: dict[str, list] = {}
        for c in Y.columns:
            split.setdefault(assigned.get(c, "other"), []).append(c)
        t0 = time.time()
        self.members_ = {g: self.factory(**self.kw).fit(X, Y[cols], groups=groups) for g, cols in split.items()}
        self.fit_seconds_ = time.time() - t0
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        t0 = time.time()
        p = pd.concat([m.predict(X) for m in self.members_.values()], axis=1)[self.targets_]
        p = self._shift(X, p, +1)
        self.predict_us_per_row_ = 1e6 * (time.time() - t0) / max(len(X), 1)
        return p

    def _fit(self, X: np.ndarray, Y: np.ndarray, groups) -> None:  # pragma: no cover - fit is overridden
        raise NotImplementedError

    def _predict(self, X: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError
