"""Per-output scikit-learn emulators: gradient boosting and ridge (linear reference)."""

from __future__ import annotations

import numpy as np

from .base import Emulator, Scaler


class _PerTarget(Emulator):
    """One model per output, fitted on the rows where that output is not missing."""

    def _make(self):
        raise NotImplementedError

    def _fit(self, X, Y, groups):
        self.xs = Scaler().fit(X)
        x = self.xs.transform(X)
        self.models_ = []
        for k in range(Y.shape[1]):
            ok = np.isfinite(Y[:, k])
            m = self._make()
            m.fit(x[ok], Y[ok, k])
            self.models_.append(m)

    def _predict(self, X):
        x = self.xs.transform(X)
        return np.column_stack([m.predict(x) for m in self.models_])


class GBEmulator(_PerTarget):
    name = "gb"

    def __init__(self, max_iter: int = 500, learning_rate: float = 0.05, max_leaf_nodes: int = 63,
                 l2_regularization: float = 1.0, seed: int = 0):
        self.params = dict(max_iter=max_iter, learning_rate=learning_rate, max_leaf_nodes=max_leaf_nodes,
                           l2_regularization=l2_regularization, early_stopping=True, validation_fraction=0.1,
                           n_iter_no_change=20, random_state=seed)

    def _make(self):
        from sklearn.ensemble import HistGradientBoostingRegressor

        return HistGradientBoostingRegressor(**self.params)


class RidgeEmulator(_PerTarget):
    name = "ridge"

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def _make(self):
        from sklearn.linear_model import Ridge

        return Ridge(alpha=self.alpha)
