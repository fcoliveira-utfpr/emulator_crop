"""Package simulated datasets for a GitHub release (one zip per dataset + SHA256SUMS).

Usage (repository root):

    python benchmark/package_dataset.py dssat_v3 aquacrop_v3 --out dist/data-v3

Each ``data/<name>/`` folder is zipped (parquet is already compressed: stored, not deflated)
with ``README_data.md`` and ``LICENSE-data.txt`` from ``benchmark/data_release/``. Local paths
in ``meta.json`` (executables, source folders) are replaced by neutral descriptions. The
``benchmark/`` subfolder (emulator predictions) and ``features*.parquet`` caches are left out.
Download them back with :func:`cropemu_bench.datasets.fetch_dataset`.
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRA = ROOT / "benchmark" / "data_release"
SKIP_DIRS = {"benchmark"}
SKIP_PREFIX = ("features",)


def clean_meta(meta: dict, name: str) -> dict:
    """``meta.json`` without the paths of the machine that ran the simulations."""
    out = dict(meta)
    if "dssat" in out:
        out["dssat"] = "DSSAT 4.8.5 CROPGRO-Soybean (DSCSM048)"
    if "executable" in out:
        out["executable"] = "AquaCrop 7.3 (release v7.3_typofix)"
    if "seasons_from" in out:
        out["seasons_from"] = Path(str(out["seasons_from"]).replace("\\", "/")).name
    out["dataset"] = name
    return out


def package(name: str, out_dir: Path) -> Path:
    src = ROOT / "data" / name
    if not (src / "meta.json").is_file():
        raise FileNotFoundError(f"{src} is not a dataset folder (no meta.json)")
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f"{name}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED) as z:
        for f in sorted(src.rglob("*")):
            rel = f.relative_to(src)
            if f.is_dir() or rel.parts[0] in SKIP_DIRS or rel.name.startswith(SKIP_PREFIX):
                continue
            if rel.name == "meta.json":
                meta = json.loads(f.read_text(encoding="utf-8"))
                z.writestr(f"{name}/meta.json", json.dumps(clean_meta(meta, name), indent=1))
            else:
                z.write(f, f"{name}/{rel.as_posix()}")
        for extra in ("README_data.md", "LICENSE-data.txt"):
            if (EXTRA / extra).is_file():
                z.write(EXTRA / extra, f"{name}/{extra}")
    return zpath


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+", help="dataset folders in data/")
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "data")
    args = ap.parse_args()
    sums = args.out / "SHA256SUMS"
    lines = dict(ln.split("  ", 1)[::-1] for ln in sums.read_text().splitlines()) if sums.is_file() else {}
    for name in args.names:
        z = package(name, args.out)
        lines[z.name] = sha256(z)
        print(f"{z.name}: {z.stat().st_size / 1e6:.0f} MB  sha256 {lines[z.name]}", flush=True)
    sums.write_text("".join(f"{h}  {n}\n" for n, h in sorted(lines.items())))


if __name__ == "__main__":
    main()
