"""Emulators that also read the daily weather of the season (:mod:`cropemu_bench.sequence`).

``ConvEmulator``: a 1-D convolutional network over the daily sequence (Tmax, Tmin, radiation,
rain, ETo, VPD, day length, bucket stress, day after sowing; 30 days before to 170 after sowing),
whose embedding (mean and max over time) is joined to the season inputs; a dense head predicts
the outputs. It sees *when* heat, drought or rain happen in the cycle, which the fixed 30-day
windows blur (benchmark/improve: yield RMSE 454 -> 335 kg/ha on dssat_v1, block validation).

``SequenceEmulator``: the development dates from the mean of several MLPs (seeds) on the season
inputs, everything else from a ``ConvEmulator`` (the convolutional network did not improve the
dates; the seed mean did).

Both take the sequences as an extra argument: ``fit(X, Y, groups, seq)``, ``predict(X, seq)``,
with ``seq`` aligned with the rows of ``X`` (array seasons x channels x days).
"""

from __future__ import annotations

import copy
import time

import numpy as np
import pandas as pd

from .base import Scaler
from .grouped import PHENOLOGY, GroupedEmulator
from .mlp import MLPEmulator


def _conv_net_class():
    import torch
    import torch.nn as nn

    class ConvNet(nn.Module):
        """Convolutional embedding of the daily sequence (mean and max over time) + dense layer on the
        season inputs, joined by a dense head."""

        def __init__(self, n_static: int, n_out: int, channels: int):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(channels, 32, 7, padding=3), nn.SiLU(), nn.MaxPool1d(2),
                nn.Conv1d(32, 48, 5, padding=2), nn.SiLU(), nn.MaxPool1d(2),
                nn.Conv1d(48, 64, 5, padding=2), nn.SiLU(), nn.MaxPool1d(2),
                nn.Conv1d(64, 64, 3, padding=1), nn.SiLU())
            self.static = nn.Sequential(nn.Linear(n_static, 256), nn.SiLU())
            self.head = nn.Sequential(nn.Linear(256 + 128, 256), nn.SiLU(), nn.Linear(256, 256), nn.SiLU(),
                                      nn.Linear(256, n_out))

        def forward(self, s, x):
            h = self.conv(s)
            h = torch.cat([h.mean(2), h.amax(2)], 1)
            return self.head(torch.cat([self.static(x), h], 1))

    ConvNet.__module__ = __name__
    ConvNet.__qualname__ = "ConvNet"
    return ConvNet


def __getattr__(name):                     # module-level ConvNet (picklable) without importing torch eagerly
    if name == "ConvNet":
        globals()["ConvNet"] = cls = _conv_net_class()
        return cls
    raise AttributeError(name)


def conv_net(n_static: int, n_out: int, channels: int):
    from . import sequence

    return sequence.ConvNet(n_static, n_out, channels)


class ConvEmulator:
    """1-D CNN over the daily sequence + the season inputs; NaN targets masked; early stopping on
    whole groups (spatial blocks) held out from the training data."""

    name = "conv"

    def __init__(self, lr: float = 1e-3, weight_decay: float = 1e-5, batch_size: int = 512, max_epochs: int = 120,
                 patience: int = 12, val_fraction: float = 0.1, seed: int = 0, threads: int | None = 4,
                 verbose: bool = True):
        self.lr, self.weight_decay, self.batch_size = lr, weight_decay, batch_size
        self.max_epochs, self.patience, self.val_fraction = max_epochs, patience, val_fraction
        self.seed, self.threads, self.verbose = seed, threads, verbose

    def fit(self, X: pd.DataFrame, Y: pd.DataFrame, groups=None, seq=None) -> "ConvEmulator":
        import torch

        if seq is None or len(seq) != len(X):
            raise ValueError("seq: one daily sequence per row of X")
        if self.threads:
            torch.set_num_threads(self.threads)
        self.features_, self.targets_ = list(X.columns), list(Y.columns)
        t0 = time.time()
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        Xa, Ya = X.to_numpy(float), Y.to_numpy(float)
        n = len(Xa)
        self.xs, self.ys = Scaler().fit(Xa), Scaler().fit(Ya)
        sample = np.asarray(seq[rng.choice(n, size=min(5000, n), replace=False)], np.float32)
        self.cm, self.cs = sample.mean((0, 2)), sample.std((0, 2)) + 1e-6
        S = self._seq_tensor(seq)
        x = torch.from_numpy(self.xs.transform(Xa).astype(np.float32))
        y = self.ys.transform(Ya).astype(np.float32)
        mask = torch.from_numpy(np.isfinite(y).astype(np.float32))
        y = torch.from_numpy(np.nan_to_num(y))
        idx = np.arange(n)
        if groups is not None:
            g = np.asarray(groups)
            ug = np.unique(g)
            val_g = rng.choice(ug, size=max(1, round(self.val_fraction * len(ug))), replace=False)
            is_val = np.isin(g, val_g)
        else:
            is_val = rng.random(n) < self.val_fraction
        val, fit = idx[is_val], idx[~is_val]
        net = conv_net(Xa.shape[1], Ya.shape[1], seq.shape[1])
        opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=self.patience // 3)
        loss = lambda p, t, m: ((p - t) ** 2 * m).sum() / m.sum().clamp(min=1)

        def val_loss():
            net.eval()
            tot, w = 0.0, 0.0
            with torch.no_grad():
                for i in range(0, len(val), 4096):
                    b = val[i:i + 4096]
                    m = mask[b]
                    tot += float(((net(S(b), x[b]) - y[b]) ** 2 * m).sum())
                    w += float(m.sum())
            return tot / max(w, 1)

        best, best_state, wait = np.inf, None, 0
        self.history_ = []
        for epoch in range(self.max_epochs):
            te = time.time()
            net.train()
            perm = rng.permutation(fit)
            for i in range(0, len(perm), self.batch_size):
                b = perm[i:i + self.batch_size]
                opt.zero_grad()
                loss(net(S(b), x[b]), y[b], mask[b]).backward()
                opt.step()
            v = val_loss()
            sched.step(v)
            self.history_.append(v)
            if v < best - 1e-5:
                best, best_state, wait = v, copy.deepcopy(net.state_dict()), 0
            else:
                wait += 1
            if self.verbose:
                print(f"    epoch {epoch}: val {v:.4f} ({time.time() - te:.0f}s)", flush=True)
            if wait >= self.patience:
                break
        net.load_state_dict(best_state)
        self.net_ = net.eval()
        self.epochs_ = epoch + 1
        self.fit_seconds_ = time.time() - t0
        return self

    def _seq_tensor(self, seq):
        import torch

        cm, cs = self.cm[None, :, None], self.cs[None, :, None]
        return lambda idx: torch.from_numpy((np.asarray(seq[idx], np.float32) - cm) / cs)

    def predict(self, X: pd.DataFrame, seq=None) -> pd.DataFrame:
        import torch

        t0 = time.time()
        x = torch.from_numpy(self.xs.transform(X[self.features_].to_numpy(float)).astype(np.float32))
        S = self._seq_tensor(seq)
        out = []
        with torch.no_grad():
            for i in range(0, len(x), 4096):
                b = np.arange(i, min(i + 4096, len(x)))
                out.append(self.net_(S(b), x[b]).numpy())
        p = self.ys.inverse(np.concatenate(out)) if out else np.empty((0, len(self.targets_)))
        self.predict_us_per_row_ = 1e6 * (time.time() - t0) / max(len(X), 1)
        return pd.DataFrame(p, index=X.index, columns=self.targets_)


class SequenceEmulator:
    """Dates: mean of ``GroupedEmulator`` phenology networks with seeds ``seeds`` (``offsets`` as in
    :class:`GroupedEmulator`); other outputs: :class:`ConvEmulator`."""

    name = "cnn"

    def __init__(self, seeds=(0, 1, 2, 3), offsets: dict | None = None, conv: dict | None = None,
                 phenology=PHENOLOGY, verbose: bool = True):
        self.seeds, self.offsets, self.conv = tuple(seeds), dict(offsets or {}), dict(conv or {})
        self.phenology, self.verbose = tuple(phenology), verbose

    def split(self, Y: pd.DataFrame) -> tuple[list, list]:
        dates = [c for c in Y.columns if c in self.phenology]
        return dates, [c for c in Y.columns if c not in dates]

    def fit_dates_factory(self, seed: int = 0) -> GroupedEmulator:
        """Unfitted date network of one seed (fit it on the date columns only)."""
        return GroupedEmulator(factory=MLPEmulator, offsets=self.offsets, seed=seed)

    def conv_factory(self) -> ConvEmulator:
        return ConvEmulator(**{"verbose": self.verbose, **self.conv})

    def fit(self, X: pd.DataFrame, Y: pd.DataFrame, groups=None, seq=None) -> "SequenceEmulator":
        t0 = time.time()
        self.features_, self.targets_ = list(X.columns), list(Y.columns)
        dates, other = self.split(Y)
        self.date_members_ = []
        for s in self.seeds:
            self.date_members_.append(self.fit_dates_factory(s).fit(X, Y[dates], groups=groups))
            if self.verbose:
                print(f"  dates seed {s}: {(time.time() - t0) / 60:.1f} min", flush=True)
        self.conv_ = self.conv_factory().fit(X, Y[other], groups=groups, seq=seq)
        self.fit_seconds_ = time.time() - t0
        return self

    def predict(self, X: pd.DataFrame, seq=None) -> pd.DataFrame:
        t0 = time.time()
        d = sum(m.predict(X) for m in self.date_members_) / len(self.date_members_)
        p = pd.concat([d, self.conv_.predict(X, seq)], axis=1)[self.targets_]
        self.predict_us_per_row_ = 1e6 * (time.time() - t0) / max(len(X), 1)
        return p
