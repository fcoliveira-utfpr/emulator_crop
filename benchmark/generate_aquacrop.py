"""AquaCrop v7 dataset on the seasons of a DSSAT dataset (same points, years, sowing, regime, climate).

Usage (after benchmark/generate_dssat.py):

    CROPEMU_AQUACROP_EXE=.../aquacrop CROPEMU_AQUACROP_DATA=.../DATA \\
        python benchmark/generate_aquacrop.py --seasons-from dssat_v0 --name aquacrop_v0

Writes data/<name>/ (see cropemu_bench.pipeline_aquacrop.generate).
"""

import argparse
import time
from pathlib import Path

from cropemu_bench.pipeline_aquacrop import generate

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons-from", default="dssat_v0", help="DSSAT dataset in data/ whose seasons are simulated")
    ap.add_argument("--name", default="aquacrop_v0")
    ap.add_argument("--crop", default="SoybeanGDD", help="FAO crop file (without .CRO)")
    ap.add_argument("--jobs", type=int, default=4, help="AquaCrop processes")
    args = ap.parse_args()
    t0 = time.time()
    out = generate(ROOT / "data" / args.seasons_from, ROOT / "data" / args.name, crop_name=args.crop, n_jobs=args.jobs)
    print(f"done in {(time.time() - t0) / 60:.1f} min -> {out}", flush=True)


if __name__ == "__main__":
    main()
