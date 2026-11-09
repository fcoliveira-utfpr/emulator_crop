"""Export of a trained emulator to the library format: ONNX graph + card (``cropemu.Emulator``).

The graph takes the inputs in the card order (float32, any number of rows) and returns
the outputs in the card order. Scaling, the members of a grouped emulator and the
thermal-time offsets are inside the graph, so the library needs only onnxruntime.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .emulators.grouped import GroupedEmulator
from .emulators.mlp import MLPEmulator

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
    """A torch module computing ``em.predict`` on a float32 array of the inputs."""
    import torch
    import torch.nn as nn

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


def export(em, X: pd.DataFrame, folder, card: dict, check_rows: int = 2000) -> Path:
    """Write ``model.onnx`` and ``card.json`` of a fitted emulator to ``folder``.

    ``X``: the training inputs (domain of every input: 0.5/99.5 % quantiles, min and max).
    ``card``: name, model, crop, cultivar parameters, thermal, acceptance, training description...
    The ONNX predictions are checked against ``em.predict`` on ``check_rows`` rows.
    """
    import onnxruntime as ort
    import torch

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    X = X[em.features_]
    g = torch_graph(em)
    x = torch.tensor(X.iloc[:16].to_numpy("float32"))
    torch.onnx.export(g, x, folder / "model.onnx", input_names=["inputs"], output_names=["outputs"],
                      dynamic_axes={"inputs": {0: "rows"}, "outputs": {0: "rows"}}, opset_version=17)
    rows = X.sample(min(check_rows, len(X)), random_state=0)
    sess = ort.InferenceSession(str(folder / "model.onnx"), providers=["CPUExecutionProvider"])
    p_onnx = sess.run(None, {"inputs": rows.to_numpy("float32")})[0]
    p_ref = em.predict(rows).to_numpy()
    scale = np.nanstd(p_ref, axis=0) + 1e-9
    err = float(np.nanmax(np.abs(p_onnx - p_ref) / scale))
    if err > 1e-3:
        raise RuntimeError(f"ONNX differs from the emulator: {err:.2g} SD")
    q = X.quantile([0.005, 0.995])
    card = {"card_version": CARD_VERSION, **card, "inputs": list(em.features_), "outputs": list(em.targets_),
            "domain": {c: {"q005": float(q.loc[0.005, c]), "q995": float(q.loc[0.995, c]),
                           "min": float(X[c].min()), "max": float(X[c].max())} for c in X},
            "onnx": {"file": "model.onnx", "input": "inputs", "output": "outputs", "max_rel_error_check": err}}
    (folder / "card.json").write_text(json.dumps(card, indent=1, default=float))
    return folder
