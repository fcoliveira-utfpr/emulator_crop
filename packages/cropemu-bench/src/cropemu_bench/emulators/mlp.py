"""Multi-output MLP (PyTorch): one network for every output, NaN targets masked in the loss."""

from __future__ import annotations

import copy

import numpy as np

from .base import Emulator, Scaler


class MLPEmulator(Emulator):
    name = "mlp"

    def __init__(self, hidden=(256, 256, 256), lr: float = 1e-3, weight_decay: float = 1e-5,
                 batch_size: int = 512, max_epochs: int = 300, patience: int = 20, val_fraction: float = 0.1,
                 seed: int = 0, threads: int | None = None, verbose: bool = False):
        self.hidden, self.lr, self.weight_decay = tuple(hidden), lr, weight_decay
        self.batch_size, self.max_epochs, self.patience = batch_size, max_epochs, patience
        self.val_fraction, self.seed, self.threads, self.verbose = val_fraction, seed, threads, verbose

    def _net(self, n_in, n_out):
        import torch.nn as nn

        layers, d = [], n_in
        for h in self.hidden:
            layers += [nn.Linear(d, h), nn.SiLU()]
            d = h
        layers.append(nn.Linear(d, n_out))
        return nn.Sequential(*layers)

    def _fit(self, X, Y, groups):
        import torch

        if self.threads:
            torch.set_num_threads(self.threads)
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        self.xs, self.ys = Scaler().fit(X), Scaler().fit(Y)
        x = self.xs.transform(X).astype("float32")
        y = self.ys.transform(Y).astype("float32")
        mask = np.isfinite(y)
        y = np.nan_to_num(y)

        # validation split for early stopping: whole groups (e.g. spatial blocks) when given
        if groups is not None:
            ug = np.unique(groups)
            val_groups = rng.choice(ug, size=max(1, int(round(len(ug) * self.val_fraction))), replace=False)
            val = np.isin(groups, val_groups)
        else:
            val = rng.random(len(x)) < self.val_fraction
        tr = ~val
        t = lambda a: torch.from_numpy(np.ascontiguousarray(a))
        xt, yt, mt = t(x[tr]), t(y[tr]), t(mask[tr].astype("float32"))
        xv, yv, mv = t(x[val]), t(y[val]), t(mask[val].astype("float32"))

        net = self._net(x.shape[1], y.shape[1])
        opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=self.patience // 3)

        def loss(pred, target, m):
            return ((pred - target) ** 2 * m).sum() / m.sum().clamp(min=1)

        best, best_state, wait = np.inf, None, 0
        self.history_ = []
        for epoch in range(self.max_epochs):
            net.train()
            perm = torch.randperm(len(xt))
            for i in range(0, len(xt), self.batch_size):
                b = perm[i:i + self.batch_size]
                opt.zero_grad()
                loss(net(xt[b]), yt[b], mt[b]).backward()
                opt.step()
            net.eval()
            with torch.no_grad():
                v = float(loss(net(xv), yv, mv))
            sched.step(v)
            self.history_.append(v)
            if v < best - 1e-5:
                best, best_state, wait = v, copy.deepcopy(net.state_dict()), 0
            else:
                wait += 1
                if wait >= self.patience:
                    break
            if self.verbose and epoch % 10 == 0:
                print(f"epoch {epoch}: val loss {v:.4f}")
        net.load_state_dict(best_state)
        self.net_ = net.eval()
        self.epochs_ = epoch + 1

    def _predict(self, X):
        import torch

        with torch.no_grad():
            p = self.net_(torch.from_numpy(self.xs.transform(X).astype("float32"))).numpy()
        return self.ys.inverse(p)
