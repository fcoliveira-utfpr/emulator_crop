"""Export of a trained emulator to the library format: ONNX graph + card (``cropemu.Emulator``).

The graph takes the inputs in the card order (float32, any number of rows) and returns
the outputs in the card order. Scaling, the members of a grouped emulator and the
thermal-time offsets are inside the graph, so the library needs only onnxruntime.
"""

from __future__ import annotations

import inspect

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .emulators.grouped import GroupedEmulator
from .emulators.mlp import MLPEmulator
from .emulators.sequence import SequenceEmulator

CARD_VERSION = 1


def _members(em) -> list[tuple]:
    """(fitted MLP, output names) of an MLP or a grouped emulator of MLPs."""
    if isinstance(em, MLPEmulator):
        return [(em, em.targets_)]
    if isinstance(em, GroupedEmulator):
        out = []
        for m in em.members_.values():
            if not isinstance(m, MLPEmulator):
                raise TypeError(f"only MLP members can be exported, not {type(m).__name__}")
            out.append((m, m.targets_))
        return out
    raise TypeError(f"cannot export {type(em).__name__}")


def torch_graph(em):
    """A torch module computing ``em.predict`` on a float32 array of the inputs (and, for a
    :class:`SequenceEmulator`, the daily sequences: ``forward(inputs, sequence)``)."""
    import torch
    import torch.nn as nn

    if isinstance(em, SequenceEmulator):
        return _sequence_graph(em)
    features, targets = list(em.features_), list(em.targets_)
    f32 = lambda a: torch.tensor(np.asarray(a, dtype="float32"))

    class Member(nn.Module):
        def __init__(self, m):
            super().__init__()
            self.net = m.net_
            for k, v in (("xm", m.xs.mean), ("xs", m.xs.std), ("ym", m.ys.mean), ("ys", m.ys.std)):
                self.register_buffer(k, f32(v))
            self.idx = [features.index(c) for c in m.features_]

        def forward(self, x):
            return self.net((x[:, self.idx] - self.xm) / self.xs) * self.ys + self.ym

    class Graph(nn.Module):
        def __init__(self):
            super().__init__()
            members = _members(em)
            self.members = nn.ModuleList(Member(m) for m, _ in members)
            order = [c for _, cols in members for c in cols]
            self.perm = [order.index(c) for c in targets]
            offsets = getattr(em, "offsets_", {})
            m = np.zeros((len(features), len(targets)), dtype="float32")      # output += input @ m
            for c, f in offsets.items():
                m[features.index(f), targets.index(c)] = 1.0
            self.has_offsets = bool(offsets)
            self.register_buffer("offsets", torch.tensor(m))

        def forward(self, x):
            y = torch.cat([m(x) for m in self.members], dim=1)[:, self.perm]
            return y + x @ self.offsets if self.has_offsets else y

    return Graph().eval()


def _sequence_graph(em: SequenceEmulator):
    """Graph of a :class:`SequenceEmulator`: mean of the date networks + the convolutional network."""
    import torch
    import torch.nn as nn

    features, targets = list(em.features_), list(em.targets_)
    f32 = lambda a: torch.tensor(np.asarray(a, dtype="float32"))

    class Dates(nn.Module):                       # one seed: a grouped emulator with one (date) member
        def __init__(self, g):
            super().__init__()
            (m,) = g.members_.values()
            self.net = m.net_
            for k, v in (("xm", m.xs.mean), ("xs", m.xs.std), ("ym", m.ys.mean), ("ys", m.ys.std)):
                self.register_buffer(k, f32(v))
            self.idx = [features.index(c) for c in m.features_]
            self.perm = [list(m.targets_).index(c) for c in g.targets_]
            off = np.zeros((len(features), len(g.targets_)), dtype="float32")
            for c, f in g.offsets_.items():
                off[features.index(f), list(g.targets_).index(c)] = 1.0
            self.register_buffer("off", torch.tensor(off))

        def forward(self, x):
            return (self.net((x[:, self.idx] - self.xm) / self.xs) * self.ys + self.ym)[:, self.perm] + x @ self.off

    class Conv(nn.Module):
        def __init__(self, c):
            super().__init__()
            self.net = c.net_
            for k, v in (("xm", c.xs.mean), ("xs", c.xs.std), ("ym", c.ys.mean), ("ys", c.ys.std)):
                self.register_buffer(k, f32(v))
            self.register_buffer("cm", f32(c.cm)[None, :, None])
            self.register_buffer("cs", f32(c.cs)[None, :, None])
            self.idx = [features.index(f) for f in c.features_]

        def forward(self, x, s):
            return self.net((s - self.cm) / self.cs, (x[:, self.idx] - self.xm) / self.xs) * self.ys + self.ym

    class Graph(nn.Module):
        def __init__(self):
            super().__init__()
            self.dates = nn.ModuleList(Dates(g) for g in em.date_members_)
            self.conv = Conv(em.conv_)
            order = list(em.date_members_[0].targets_) + list(em.conv_.targets_)
            self.perm = [order.index(c) for c in targets]

        def forward(self, x, s):
            d = sum(m(x) for m in self.dates) / len(self.dates)
            return torch.cat([d, self.conv(x, s)], dim=1)[:, self.perm]

    return Graph().eval()


def export(em, X: pd.DataFrame, folder, card: dict, check_rows: int = 2000, seq=None) -> Path:
    """Write ``model.onnx`` and ``card.json`` of a fitted emulator to ``folder``.

    ``X``: the training inputs (domain of every input: 0.5/99.5 % quantiles, min and max).
    ``card``: name, model, crop, cultivar parameters, thermal, acceptance, training description...
    ``seq``: the daily sequences of the rows of ``X`` (needed for a :class:`SequenceEmulator`,
    whose graph has a second input, ``sequence``: rows x channels x days).
    The ONNX predictions are checked against ``em.predict`` on ``check_rows`` rows.
    """
    import onnxruntime as ort
    import torch

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    X = X[em.features_]
    g = torch_graph(em)
    seqs = isinstance(em, SequenceEmulator)
    x = torch.tensor(X.iloc[:16].to_numpy("float32"))
    # TorchScript exporter: torch >= 2.9 defaults to the dynamo exporter, which needs onnxscript
    legacy = {"dynamo": False} if "dynamo" in inspect.signature(torch.onnx.export).parameters else {}
    if seqs:
        s = torch.tensor(np.asarray(seq[:16], dtype="float32"))
        torch.onnx.export(g, (x, s), folder / "model.onnx", input_names=["inputs", "sequence"],
                          output_names=["outputs"], opset_version=17, **legacy,
                          dynamic_axes={"inputs": {0: "rows"}, "sequence": {0: "rows"}, "outputs": {0: "rows"}})
    else:
        torch.onnx.export(g, x, folder / "model.onnx", input_names=["inputs"], output_names=["outputs"],
                          dynamic_axes={"inputs": {0: "rows"}, "outputs": {0: "rows"}}, opset_version=17, **legacy)
    pick = np.sort(np.random.default_rng(0).choice(len(X), min(check_rows, len(X)), replace=False))
    rows = X.iloc[pick]
    sess = ort.InferenceSession(str(folder / "model.onnx"), providers=["CPUExecutionProvider"])
    feed = {"inputs": rows.to_numpy("float32")}
    if seqs:
        rs = np.asarray(seq[pick], dtype="float32")
        feed["sequence"] = rs
        p_ref = em.predict(rows, rs).to_numpy()
    else:
        p_ref = em.predict(rows).to_numpy()
    p_onnx = sess.run(None, feed)[0]
    scale = np.nanstd(p_ref, axis=0) + 1e-9
    err = float(np.nanmax(np.abs(p_onnx - p_ref) / scale))
    if err > 1e-3:
        raise RuntimeError(f"ONNX differs from the emulator: {err:.2g} SD")
    q = X.quantile([0.005, 0.995])
    card = {"card_version": CARD_VERSION, **card, "inputs": list(em.features_), "outputs": list(em.targets_),
            "domain": {c: {"q005": float(q.loc[0.005, c]), "q995": float(q.loc[0.995, c]),
                           "min": float(X[c].min()), "max": float(X[c].max())} for c in X},
            "onnx": {"file": "model.onnx", "input": "inputs", "output": "outputs", "max_rel_error_check": err}}
    if seqs:
        from cropemu.features import SEQUENCE_CHANNELS, SEQUENCE_DAYS

        card["onnx"]["sequence_input"] = "sequence"
        card["sequence"] = {"channels": list(SEQUENCE_CHANNELS), "days": list(SEQUENCE_DAYS)}
    (folder / "card.json").write_text(json.dumps(card, indent=1, default=float))
    return folder
