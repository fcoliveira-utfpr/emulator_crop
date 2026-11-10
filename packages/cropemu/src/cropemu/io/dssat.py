"""Read DSSAT files (weather, soil, cultivar, experiment and observed data) into cropemu tables.

Many published field experiments are distributed in DSSAT format (e.g. the DSSAT example data,
https://github.com/DSSAT/dssat-csm-data). These readers turn them into the cropemu standard
weather table and soil profile, so the emulators can be run on station weather, measured soils
and real treatments, and compared with the observations.

>>> w = read_wth("UFGA7801.WTH")                       # station weather, standard columns
>>> s = read_sol("SOIL.SOL", "IBSB910015")              # measured soil profile (ll, dul, sat)
>>> c = read_cul("SBGRO048.CUL", "IB0001")              # cultivar coefficients
>>> x = read_experiment("UFGA7801.SBX")                 # one row per treatment
>>> obs = read_observed("UFGA7801.SBA")                 # observed summary data (FileA)

Two-digit years (``YYDDD``) are read as 2000-2049 below 50 and 1950-1999 otherwise.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

MISSING = -99.0


# ---------------------------------------------------------------------------- generic parsing
def _tokens(header: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", header)]


def _row(header: str, line: str) -> dict:
    """Values of a data line under a DSSAT ``@`` header.

    Whitespace splitting when it gives as many values as columns (extra words go to the last
    column). Otherwise (dotted text columns such as ``TNAME....``, or blank fields) by position:
    a dotted column takes the text from its start to the next column; every other value goes to
    the column it overlaps most (values may be right- or left-aligned under their header).
    """
    toks = _tokens(header)
    names = [t[0].lstrip("@").strip(".") or t[0] for t in toks]
    parts = line.split()
    dotted = [".." in t[0] and not t[0].startswith("..") for t in toks]
    if not any(dotted) and len(parts) >= len(toks):
        vals = parts[:len(toks) - 1] + [" ".join(parts[len(toks) - 1:])]
        return dict(zip(names, vals))
    out = {n: "" for n in names}
    text_spans = []
    for i, (tok, start, end) in enumerate(toks):
        if dotted[i]:
            hi = toks[i + 1][1] if i + 1 < len(toks) else len(line)
            out[names[i]] = line[start:hi].strip()
            text_spans.append((start, hi))
    for m in re.finditer(r"\S+", line):
        vs, ve = m.start(), m.end()
        if any(lo <= vs < hi for lo, hi in text_spans):
            continue
        best, score = None, None
        for i, (tok, start, end) in enumerate(toks):
            if dotted[i]:
                continue
            ov = min(ve, end) - max(vs, start)
            sc = (ov, -abs(ve - end))
            if score is None or sc > score:
                best, score = i, sc
        out[names[best]] = (out[names[best]] + " " + m.group()).strip()
    return out


def _number(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return v if v not in ("", None) else np.nan
    return np.nan if x <= MISSING + 1e-9 and x >= MISSING - 1e-9 else x


def _tables(lines: list[str]) -> list[pd.DataFrame]:
    """Every ``@`` header block of ``lines`` as a table (strings and numbers, -99 as NaN)."""
    out, header, rows = [], None, []
    for ln in lines + ["@"]:
        if ln.startswith("@"):
            if header is not None and rows:
                out.append(pd.DataFrame(rows))
            header, rows = (ln.rstrip() if ln.strip() != "@" else None), []
        elif header is not None and ln.strip() and not ln.startswith(("!", "*", "$")):
            rows.append({k: _number(v) for k, v in _row(header, ln.rstrip("\n")).items()})
    return out


def _text(path) -> list[str]:
    return Path(path).read_text(errors="replace").splitlines()


def dssat_date(v) -> pd.Timestamp | None:
    """``YYDDD`` or ``YYYYDDD`` (int, float or str) to a date; missing values give ``None``."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    s = str(int(float(v)))
    if int(s) < 0:
        return None
    if len(s) <= 5:
        yy, doy = int(s[:-3] or 0), int(s[-3:])
        year = 2000 + yy if yy < 50 else 1900 + yy
    else:
        year, doy = int(s[:-3]), int(s[-3:])
    return pd.Timestamp(year, 1, 1) + pd.Timedelta(days=doy - 1)


# ---------------------------------------------------------------------------- weather
def _wind_2m(u, height):
    """Wind at 2 m from wind at ``height`` m (FAO-56 eq. 47)."""
    if height is None or not math.isfinite(height) or height <= 0 or abs(height - 2) < 1e-6:
        return u
    return u * 4.87 / math.log(67.8 * height - 5.42)


def read_wth(*paths) -> pd.DataFrame:
    """Daily weather from one or more DSSAT ``.WTH`` files (e.g. one per year), in the cropemu
    standard format: ``srad`` MJ/m²/d, ``tmax``/``tmin``/``dewp`` °C, ``rain`` mm, ``wind`` m/s
    at 2 m (DSSAT gives km/d at ``WNDHT``), ``rhum`` %. ``attrs``: ``lat``, ``lon``, ``elev``,
    ``station``, ``source``. Missing values are NaN (check with :func:`cropemu.weather.check`)."""
    frames, site = [], {}
    for path in paths:
        lines = _text(path)
        hdr = [i for i, ln in enumerate(lines) if ln.startswith("@")]
        if len(hdr) < 2:
            raise ValueError(f"{path}: not a DSSAT weather file")
        info = _row(lines[hdr[0]], next(ln for ln in lines[hdr[0] + 1:] if ln.strip()))
        site = site or info
        df = pd.DataFrame([{k: _number(v) for k, v in _row(lines[hdr[1]], ln).items()}
                           for ln in lines[hdr[1] + 1:] if ln.strip() and not ln.startswith(("!", "@", "*"))])
        df.index = pd.DatetimeIndex([dssat_date(d) for d in df.pop("DATE")], name="date")
        height = _number(info.get("WNDHT"))
        cols = {}
        for src, dst in (("SRAD", "srad"), ("TMAX", "tmax"), ("TMIN", "tmin"), ("RAIN", "rain"),
                         ("DEWP", "dewp"), ("RHUM", "rhum")):
            if src in df and pd.to_numeric(df[src], errors="coerce").notna().any():
                cols[dst] = pd.to_numeric(df[src], errors="coerce")
        if "WIND" in df and pd.to_numeric(df["WIND"], errors="coerce").notna().any():
            u = pd.to_numeric(df["WIND"], errors="coerce") / 86.4               # km/d -> m/s
            cols["wind"] = _wind_2m(u, height if isinstance(height, float) else None)
        frames.append(pd.DataFrame(cols))
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    num = lambda k: _number(site.get(k))
    out.attrs = {"lat": num("LAT"), "lon": num("LONG"), "elev": num("ELEV"), "station": site.get("INSI"),
                 "source": "DSSAT weather file: " + ", ".join(Path(p).name for p in paths)}
    return out


# ---------------------------------------------------------------------------- soil
def read_sol(path, profile: str) -> pd.DataFrame:
    """A soil profile of a DSSAT ``.SOL`` file in the cropemu standard format, with the
    measured (or file) water limits: ``ll`` (SLLL), ``dul`` (SDUL), ``sat`` (SSAT), ``ksat``
    (SSKS, cm/h), texture (SLCL, SLSI; sand = 100 - clay - silt), ``soc`` (SLOC), ``bdod``
    (SBDM), ``cfvo``, ``nitrogen``, ``phh2o``, ``cec`` and ``srgf`` (root growth factor).
    ``attrs``: ``lat``, ``lon``, ``id``, ``name``, ``source``."""
    lines = _text(path)
    start = next((i for i, ln in enumerate(lines) if ln.startswith("*" + profile)), None)
    if start is None:
        raise KeyError(f"profile {profile!r} not in {path}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("*")), len(lines))
    block = lines[start:end]
    tables = _tables(block)
    site = next((t for t in tables if "SITE" in t), None)
    layers = next(t for t in tables if "SLB" in t and "SLLL" in t)
    g = lambda c: layers[c].astype(float) if c in layers else pd.Series(np.nan, index=layers.index)
    bottom = g("SLB")
    clay, silt = g("SLCL"), g("SLSI")
    out = pd.DataFrame({"top": bottom.shift(1, fill_value=0.0), "bottom": bottom, "clay": clay,
                        "sand": 100 - clay - silt, "silt": silt, "soc": g("SLOC"), "bdod": g("SBDM"),
                        "cfvo": g("SLCF"), "nitrogen": g("SLNI"), "phh2o": g("SLHW"), "cec": g("SCEC"),
                        "ll": g("SLLL"), "dul": g("SDUL"), "sat": g("SSAT"), "ksat": g("SSKS"),
                        "srgf": g("SRGF")})
    lat = lon = np.nan
    if site is not None:              # the site name may contain spaces: first two numbers of the line
        hdr = next(ln for ln in block if ln.startswith("@SITE"))
        m = re.search(r"\s(-?\d+\.?\d*)\s+(-?\d+\.?\d*)(\s|$)", block[block.index(hdr) + 1])
        if m:
            lat, lon = (_number(m.group(1)), _number(m.group(2)))
            lat, lon = (float(lat), float(lon))
    out.attrs = {"lat": lat, "lon": lon, "id": profile, "name": block[0][1:].split(None, 4)[-1].strip(),
                 "source": f"DSSAT soil file: {Path(path).name}"}
    return out


# ---------------------------------------------------------------------------- cultivar
def read_cul(path, var: str) -> dict:
    """Coefficients of cultivar ``var`` (``VAR#``) of a DSSAT ``.CUL`` file: name and numbers."""
    lines = _text(path)
    header = None
    for ln in lines:
        if ln.startswith("@VAR"):
            header = ln.rstrip()
        elif header and ln.startswith(var + " "):
            row = _row(header, ln.rstrip())
            return {k: _number(v) for k, v in row.items()}
    raise KeyError(f"cultivar {var!r} not in {path}")


# ---------------------------------------------------------------------------- experiments
def _sections(lines: list[str]) -> dict[str, list[str]]:
    out, name = {}, None
    for ln in lines:
        if ln.startswith("*"):
            name = re.split(r":|\s{2,}", ln[1:].strip())[0].strip().upper()
            out.setdefault(name, [])
        elif name:
            out[name].append(ln)
    return out


def read_filex(path) -> dict[str, pd.DataFrame]:
    """Sections of a DSSAT experiment file (FileX, e.g. ``.SBX``) as tables, by section name
    (``"TREATMENTS"``, ``"CULTIVARS"``, ``"FIELDS"``, ``"PLANTING DETAILS"``, ...). Sections with
    several header blocks are joined side by side on their level number (first column)."""
    out = {}
    for name, lines in _sections(_text(path)).items():
        tabs = _tables(lines)
        if not tabs:
            continue
        key = tabs[0].columns[0]
        t = tabs[0]
        for extra in tabs[1:]:
            if extra.columns[0] == key and key in ("L", "C", "P", "N") and not set(extra.columns[1:]) & set(t.columns):
                t = t.merge(extra, on=key, how="left")
            else:
                t = pd.concat([t, extra], ignore_index=True)
        out[name] = t
    return out


def read_experiment(path) -> pd.DataFrame:
    """One row per treatment of a DSSAT experiment: name, cultivar (``INGENO``, ``CNAME``),
    weather station (``WSTA``), soil profile (``ID_SOIL``), sowing date, plant population
    (plants/m²), row spacing (cm) and ``irrigated`` (an irrigation level is set)."""
    x = read_filex(path)
    t = x["TREATMENTS"].rename(columns={"N": "trno", "TNAME": "name"})
    t["trno"] = t["trno"].astype(int)
    cul = x["CULTIVARS"].drop_duplicates("C").set_index("C")
    fld = x["FIELDS"].drop_duplicates("L").set_index("L")
    pl = x["PLANTING DETAILS"].drop_duplicates("P").set_index("P")
    rows = []
    for r in t.to_dict("records"):
        c, f, p = cul.loc[r["CU"]], fld.loc[r["FL"]], pl.loc[r["MP"]]
        wsta = str(f["WSTA"])
        rows.append({"trno": r["trno"], "name": str(r["name"]).strip(), "INGENO": c["INGENO"],
                     "CNAME": c["CNAME"], "WSTA": wsta[:4], "ID_SOIL": f["ID_SOIL"],
                     "sowing": dssat_date(p["PDATE"]), "plants_m2": p.get("PPOE", np.nan),
                     "row_cm": p.get("PLRS", np.nan), "irrigated": bool(r.get("MI", 0) and r["MI"] > 0)})
    return pd.DataFrame(rows).set_index("trno")


#: Date columns of a FileA besides those ending in ``DAT`` (first pod, first seed, R5, R8, ...).
DATE_CODES = re.compile(r"(DAT|^PD1T|^PDFT|^R\dAT)$")


def read_observed(path, year: int | None = None) -> pd.DataFrame:
    """Observed summary data of a DSSAT FileA (e.g. ``.SBA``), one row per treatment (``TRNO``).

    Date columns (``ADAT``, ``MDAT``, ``PD1T``, ``R8AT``, ...) become dates. Some files give
    only the day of year: its year is ``year`` or, by default, the year of the experiment code
    in the first line (``UFGA7801SB`` -> 1978).
    """
    lines = _text(path)
    if year is None:
        m = re.search(r"[A-Z0-9]{4}(\d{2})\d{2}[A-Z]{2}", lines[0] if lines else "")
        year = dssat_date(int(m.group(1)) * 1000 + 1).year if m else None
    tabs = _tables(lines)
    df = pd.concat(tabs, ignore_index=True) if len(tabs) > 1 else tabs[0]
    df = df.groupby("TRNO", as_index=True).first()
    df.index = df.index.astype(int)
    df.index.name = "trno"

    def to_date(v):
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            return pd.NaT
        if v < 1000:
            return pd.Timestamp(year, 1, 1) + pd.Timedelta(days=int(v) - 1) if year else pd.NaT
        return dssat_date(v)

    for c in df:
        if DATE_CODES.search(str(c)):
            df[c] = pd.to_datetime([to_date(v) for v in df[c]])
    return df
