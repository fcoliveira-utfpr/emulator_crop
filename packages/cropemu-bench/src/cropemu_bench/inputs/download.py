"""Download of global datasets into the cropemu cache, with checksum verification."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

USER_AGENT = "cropemu-bench (+https://pypi.org/project/cropemu-bench/)"


def cache_dir(name: str) -> Path:
    d = Path(os.environ.get("CROPEMU_CACHE", Path.home() / ".cache" / "cropemu")) / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def fetch_file(url: str, dest: Path, md5sum: str | None = None, timeout: float = 300) -> Path:
    """Download ``url`` to ``dest`` unless it already exists with the right checksum."""
    dest = Path(dest)
    if dest.exists() and (md5sum is None or md5(dest) == md5sum):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        while block := r.read(1 << 20):
            f.write(block)
    if md5sum is not None and md5(tmp) != md5sum:
        tmp.unlink()
        raise IOError(f"checksum mismatch for {url}")
    tmp.replace(dest)
    return dest
