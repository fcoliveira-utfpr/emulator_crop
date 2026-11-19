"""Download the simulated datasets from the GitHub releases of the repository.

    from cropemu_bench.datasets import fetch_dataset
    folder = fetch_dataset("dssat_v3")       # data/dssat_v3, downloaded and unpacked if missing

Each dataset is one zip (``benchmark/package_dataset.py``) attached to a release; the SHA-256
is checked before unpacking.
"""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

REPOSITORY = "https://github.com/fcoliveira-utfpr/emulator_crop"

#: name -> (release tag, SHA-256 of ``<name>.zip``)
DATASETS = {
    "dssat_v3": ("data-v3", "7aefacc15cd3bddf7b4e9be56a7e98591e0fc49a12ba38a4cbf29019e95ca974"),
    "aquacrop_v3": ("data-v3", "ab13b2a6c5ebedc0591afb2cc17667380216ded2b531c9858ce5bf4e2bebea91"),
}


def default_data_dir() -> Path:
    """``data/`` of the repository (this file is in packages/cropemu-bench/src/cropemu_bench)."""
    return Path(__file__).resolve().parents[4] / "data"


def dataset_url(name: str) -> str:
    tag, _ = DATASETS[name]
    return f"{REPOSITORY}/releases/download/{tag}/{name}.zip"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch_dataset(name: str, data_dir=None, force: bool = False, url: str | None = None) -> Path:
    """The folder of dataset ``name``, downloaded from the release and unpacked if missing.

    ``data_dir`` defaults to the repository ``data/``. A folder that already has ``meta.json`` is
    used as it is unless ``force``. ``url`` overrides the release link (e.g. a mirror or a local file).
    """
    if name not in DATASETS:
        raise KeyError(f"unknown dataset {name!r}; available: {sorted(DATASETS)}")
    data_dir = Path(data_dir) if data_dir else default_data_dir()
    folder = data_dir / name
    if (folder / "meta.json").is_file() and not force:
        return folder
    data_dir.mkdir(parents=True, exist_ok=True)
    zpath = data_dir / f"{name}.zip.part"
    src = url or dataset_url(name)
    print(f"downloading {src}", flush=True)
    if Path(src).is_file():
        shutil.copyfile(src, zpath)
    else:
        with urllib.request.urlopen(src) as r, open(zpath, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
    expected = DATASETS[name][1]
    got = _sha256(zpath)
    if got != expected:
        zpath.unlink()
        raise ValueError(f"{name}.zip: SHA-256 {got} does not match {expected}")
    if folder.exists():
        shutil.rmtree(folder)
    with zipfile.ZipFile(zpath) as z:
        bad = [n for n in z.namelist() if not n.startswith(f"{name}/") or ".." in Path(n).parts]
        if bad:
            raise ValueError(f"{name}.zip has unexpected paths: {bad[:3]}")
        z.extractall(data_dir)
    zpath.unlink()
    return folder
