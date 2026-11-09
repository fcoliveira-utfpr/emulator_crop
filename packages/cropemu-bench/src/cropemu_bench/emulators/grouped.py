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

#: Default groups: development dates; everything else.
PHENOLOGY = ("EDAT_dap", "ADAT_dap", "MDAT_dap", "HDAT_dap")


class GroupedEmulator(Emulator):
    """``groups`` maps a group name to its outputs; outputs in no group form ``"other"``."""

    name = "grouped"

    def __init__(self, factory=MLPEmulator, groups: dict | None = None, **kw):
        self.factory, self.kw = factory, kw
        self.groups = {"phenology": PHENOLOGY} if groups is None else dict(groups)

    def fit(self, X: pd.DataFrame, Y: pd.DataFrame, groups=None) -> "GroupedEmulator":
        self.features_, self.targets_ = list(X.columns), list(Y.columns)
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
        self.predict_us_per_row_ = 1e6 * (time.time() - t0) / max(len(X), 1)
        return p

    def _fit(self, X: np.ndarray, Y: np.ndarray, groups) -> None:  # pragma: no cover - fit is overridden
        raise NotImplementedError

    def _predict(self, X: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError
