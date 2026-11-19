import hashlib
import zipfile

import pytest

from cropemu_bench import datasets


def _zip(path, name):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{name}/meta.json", "{}")
        z.writestr(f"{name}/summary/batch00000.parquet", b"x")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fetch_dataset(tmp_path, monkeypatch):
    src = tmp_path / "toy.zip"
    monkeypatch.setitem(datasets.DATASETS, "toy", ("data-test", _zip(src, "toy")))
    folder = datasets.fetch_dataset("toy", data_dir=tmp_path / "data", url=str(src))
    assert (folder / "meta.json").is_file() and (folder / "summary" / "batch00000.parquet").is_file()
    assert not list((tmp_path / "data").glob("*.part"))
    assert datasets.fetch_dataset("toy", data_dir=tmp_path / "data", url="missing") == folder   # cached


def test_fetch_dataset_bad_checksum(tmp_path, monkeypatch):
    src = tmp_path / "toy.zip"
    _zip(src, "toy")
    monkeypatch.setitem(datasets.DATASETS, "toy", ("data-test", "0" * 64))
    with pytest.raises(ValueError, match="SHA-256"):
        datasets.fetch_dataset("toy", data_dir=tmp_path / "data", url=str(src))
    assert not (tmp_path / "data" / "toy").exists()


def test_release_url():
    assert datasets.dataset_url("dssat_v3").endswith("/releases/download/data-v3/dssat_v3.zip")
