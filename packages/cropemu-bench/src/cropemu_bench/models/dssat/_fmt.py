"""Fixed-width formatting helpers for DSSAT input files."""

from __future__ import annotations

import math
from datetime import date

MISSING = -99


def is_missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def num(x, width: int, decimals: int = 3) -> str:
    """Right-aligned number in exactly ``width`` characters, dropping decimals if needed.

    Missing values become ``-99``. Raises ``ValueError`` if the value cannot fit.
    """
    if is_missing(x):
        return f"{MISSING:>{width}d}"
    x = float(x)
    for d in range(decimals, -1, -1):
        s = f"{x:{width}.{d}f}"
        if len(s) <= width:
            return s
    s = f"{x:.0f}."
    if len(s) <= width:
        return f"{s:>{width}s}"
    raise ValueError(f"{x} does not fit in {width} characters")


def yyddd(d: date) -> str:
    """DSSAT FileX date (YYDDD)."""
    return f"{d.year % 100:02d}{d.timetuple().tm_yday:03d}"


def yyyyddd(d: date) -> str:
    """DSSAT 4-digit-year date (YYYYDDD), used in weather files."""
    return f"{d.year:04d}{d.timetuple().tm_yday:03d}"


def code(i: int, width: int) -> str:
    """Base-36 code of ``i`` with ``width`` characters (uppercase, zero-padded)."""
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if i < 0 or i >= 36**width:
        raise ValueError(f"{i} does not fit in {width} base-36 characters")
    s = ""
    for _ in range(width):
        i, r = divmod(i, 36)
        s = digits[r] + s
    return s
