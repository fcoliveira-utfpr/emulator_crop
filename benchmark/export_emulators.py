"""Train the chosen emulator of a dataset on all its seasons and export it for the library.

Usage (after phase1_emulators.py and phase1_report.py):

    python benchmark/export_emulators.py --name dssat_v1 --emulator mlp_grouped --zoo-name dssat-soybean-v1

Writes data/zoo/<zoo-name>/: model.onnx and card.json (inputs, outputs, domain, acceptance
levels of the block validation, training data). Load with ``cropemu.load``.
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from cropemu_bench.dataset import CULTIVAR_FEATURES, DERIVED, DERIVED_FLOOR, build, model_of
from cropemu_bench.design.aquacrop import AQ_PERTURBATIONS
from cropemu_bench.design.cultivars import _MG_BY_LAT, MG_MAX, MG_MIN, MGTable
from cropemu_bench.emulators import GroupedEmulator, MLPEmulator
from cropemu_bench.emulators.grouped import AQUACROP_OFFSETS
from cropemu.soil.ptf import DEFAULT_METHOD
from cropemu_bench.export import export

ROOT = Path(__file__).resolve().parents[1]
FACTORIES = {"mlp": lambda: MLPEmulator(), "mlp_grouped": lambda: GroupedEmulator(),
             "mlp_offset": lambda: GroupedEmulator(offsets=AQUACROP_OFFSETS)}


def cultivar_info(aquacrop: bool) -> dict:
    """Card entries that let library users build a typical cultivar (``Emulator.cultivar``).

    DSSAT: the default coefficients of the maturity groups (CROPGRO-Soybean cultivar file,
    interpolated on a 0.25 MG grid; needs ``CROPEMU_DSSAT_HOME``). AquaCrop: the middle of the
    sampled range of every crop parameter (the cycle length, ``gdd_maturity``, is site specific).
    Both: the typical maturity group by latitude used to centre the design.
    """
    out = {"mg_by_lat": [list(r) for r in _MG_BY_LAT]}
    if aquacrop:
        mid = {k: (lo + hi) / 2 for k, (_, lo, hi) in AQ_PERTURBATIONS.items()}
        out["cultivar_defaults"] = {"cycle_factor": 1.0, **mid}
    else:
        import os
        import numpy as np
        from cropemu_bench.design.cultivars import COEFFICIENTS

        table = MGTable(os.environ["CROPEMU_DSSAT_HOME"])
        mgs = np.arange(MG_MIN, MG_MAX + 1e-9, 0.25)
        rows = np.array([table.baseline(m) for m in mgs])
        out["cultivar_by_mg"] = {"mg": [float(m) for m in mgs],
                                 **{c: [float(v) for v in rows[:, COEFFICIENTS.index(c)]]
                                    for c in CULTIVAR_FEATURES if c != "mg"}}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--emulator", required=True, choices=list(FACTORIES))
    ap.add_argument("--zoo-name", required=True)
    args = ap.parse_args()

    data = ROOT / "data" / args.name
    model = model_of(data)
    X, Y_all, info = build(data, derived=True)
    Y = Y_all.drop(columns=[c for c in DERIVED if c in Y_all])
    t0 = time.time()
    em = FACTORIES[args.emulator]().fit(X, Y, groups=info["block"])
    print(f"fit on {len(X)} seasons in {(time.time() - t0) / 60:.1f} min", flush=True)

    acc = pd.read_csv(data / "benchmark" / f"acceptance_{args.emulator}_block.csv", index_col="target")
    meta = json.loads((data / "meta.json").read_text())
    aquacrop = model == "aquacrop"
    card = {
        "name": args.zoo_name, "model": meta.get("model") or "DSSAT 4.8 CROPGRO-Soybean (official executable)", "crop": "soybean",
        "cultivar": ["cycle_factor", "gdd_maturity", *AQ_PERTURBATIONS] if aquacrop else list(CULTIVAR_FEATURES),
        "thermal": "aquacrop_soybean" if aquacrop else None, "water_balance": True, "initial_water": 0.5,
        "hydraulics": DEFAULT_METHOD, **cultivar_info(aquacrop),
        "derived": {k: [n, d, f, DERIVED_FLOOR] for k, (n, d, f) in DERIVED.items() if n in Y and d in Y},
        "acceptance": {c: {"level": r["level"], "rmse": r["rmse"], "r2": r["r2"], "relative_rmse": r["relative_rmse"],
                           "criterion": r["criterion"]} for c, r in acc.iterrows()},
        "validation": "5-fold cross-validation by 5-degree spatial blocks (out-of-fold metrics)",
        "emulator": {"type": args.emulator, "offsets": getattr(em, "offsets_", {}), "fit_minutes": (time.time() - t0) / 60},
        "training": {"dataset": args.name, "seasons": len(X), "points": int(info["point"].nunique()),
                     "weather": meta.get("weather"), "soil": meta.get("soil"), "created": time.strftime("%Y-%m-%d")},
    }
    out = export(em, X, ROOT / "data" / "zoo" / args.zoo_name, card)
    print(f"exported to {out}", flush=True)


if __name__ == "__main__":
    main()
