"""Common interface of the emulators: fit(X, Y) / predict(X) on DataFrames, NaN targets masked."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Scaler:
    """Column standardization with NaN-aware statistics (constant columns keep scale 1)."""

    def fit(self, a: np.ndarray) -> "Scaler":
        self.mean = np.nanmean(a, axis=0)
        sd = np.nanstd(a, axis=0)
        self.std = np.where(sd > 0, sd, 1.0)
        return self

    def transform(self, a):
        return (a - self.mean) / self.std

    def inverse(self, a):
        return a * self.std + self.mean


class Emulator(ABC):
    name = "emulator"

    def fit(self, X: pd.DataFrame, Y: pd.DataFrame, groups=None) -> "Emulator":
        if X.isna().any().any():
            raise ValueError(f"features with NaN: {X.columns[X.isna().any()].tolist()}")
        self.features_ = list(X.columns)
        self.targets_ = list(Y.columns)
        t0 = time.time()
        self._fit(X.to_numpy(float), Y.to_numpy(float), None if groups is None else np.asarray(groups))
        self.fit_seconds_ = time.time() - t0
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        t0 = time.time()
        p = self._predict(X[self.features_].to_numpy(float))
        self.predict_us_per_row_ = 1e6 * (time.time() - t0) / max(len(X), 1)
        return pd.DataFrame(p, index=X.index, columns=self.targets_)

    @abstractmethod
    def _fit(self, X: np.ndarray, Y: np.ndarray, groups) -> None: ...

    @abstractmethod
    def _predict(self, X: np.ndarray) -> np.ndarray: ...
