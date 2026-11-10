"""Own data from spreadsheets (CSV, Excel or a DataFrame): weather, soil profiles and seasons.

Column names are matched case- and accent-insensitively against English and Portuguese aliases,
ignoring units in parentheses or brackets (``"Chuva (mm)"`` -> ``rain``). Obvious unit mistakes are
converted with a warning (radiation in W/m² or kJ/m²/d, temperatures in K, humidity or texture as
fractions, organic matter instead of organic carbon); every conversion is recorded in
``attrs["conversions"]``.

>>> write_templates("my_data", lang="pt")          # example spreadsheets with the expected columns
>>> sites = read_sites("my_data/locais.csv")         # name, lat, lon, elev
>>> w = read_weather("my_data/clima.csv", lat=-24.5, lon=-51.6, elev=600)
>>> soils = read_soils("my_data/solo.csv")          # {profile: profile table}
>>> seasons = read_seasons("my_data/safras.csv")    # one row per season, observations as DAS
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

WEATHER = {
    "srad": ["srad", "rs", "rad", "radiation", "solar_radiation", "radiacao", "radiacao_solar", "rg"],
    "tmax": ["tmax", "t_max", "temp_max", "tx", "maximum_temperature", "temperatura_maxima", "tmaxima"],
    "tmin": ["tmin", "t_min", "temp_min", "tn", "minimum_temperature", "temperatura_minima", "tminima"],
    "rain": ["rain", "prec", "precip", "precipitation", "prcp", "rainfall", "chuva", "precipitacao", "ppt"],
    "rhum": ["rhum", "rh", "humidity", "relative_humidity", "umidade", "umidade_relativa", "ur"],
    "wind": ["wind", "u2", "ws", "wind_speed", "vento", "velocidade_do_vento"],
    "dewp": ["dewp", "tdew", "td", "dew_point", "ponto_de_orvalho", "orvalho"],
}
DATE = ["date", "data", "dia", "day", "datetime"]
YEAR, DOY = ["year", "ano"], ["doy", "day_of_year", "dia_juliano", "dia_do_ano", "jday"]
MONTH, DAY = ["month", "mes"], ["day", "dia"]

SOIL = {
    "profile": ["profile", "perfil", "site", "local", "farm", "fazenda", "id", "solo"],
    "top": ["top", "upper", "depth_top", "topo", "prof_topo", "profundidade_topo", "prof_sup", "de"],
    "bottom": ["bottom", "lower", "depth", "depth_bottom", "base", "prof_base", "profundidade",
               "profundidade_base", "prof_inf", "ate"],
    "clay": ["clay", "argila"],
    "sand": ["sand", "areia"],
    "silt": ["silt", "silte"],
    "soc": ["soc", "oc", "organic_carbon", "carbono", "carbono_organico", "c_org", "cot"],
    "om": ["om", "som", "organic_matter", "materia_organica", "mo"],
    "bdod": ["bdod", "bd", "bulk_density", "density", "densidade", "ds", "densidade_do_solo"],
    "ll": ["ll", "wilting_point", "wp1500", "pmp", "ponto_de_murcha", "ponto_de_murcha_permanente"],
    "dul": ["dul", "field_capacity", "fc", "cc", "capacidade_de_campo"],
    "sat": ["sat", "saturation", "saturacao", "porosidade", "porosity"],
    "ksat": ["ksat", "saturated_conductivity", "condutividade_saturada", "k0"],
}
SEASONS = {
    "site": ["site", "farm", "fazenda", "local", "location", "sitio"],
    "field": ["field", "plot", "talhao", "parcela", "lote"],
    "sowing": ["sowing", "planting", "sowing_date", "semeadura", "plantio", "data_de_semeadura"],
    "cultivar": ["cultivar", "variety", "variedade"],
    "mg": ["mg", "maturity_group", "gm", "grupo_de_maturacao", "grupo_de_maturidade"],
    "irrigated": ["irrigated", "irrigation", "irrigado", "irrigacao"],
    "obs_yield": ["yield", "obs_yield", "observed_yield", "produtividade", "rendimento", "prod"],
    "obs_flowering": ["flowering", "anthesis", "obs_flowering", "florescimento", "floracao", "r1"],
    "obs_maturity": ["maturity", "obs_maturity", "maturacao", "maturidade", "r7", "r8", "colheita_fisiologica"],
}
TRUE = {"1", "true", "yes", "y", "sim", "s", "x", "irrigado", "irrigated", "verdadeiro"}


# ---------------------------------------------------------------------------- helpers
def _key(name) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)                    # drop units: "chuva (mm)"
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _match(columns, aliases: dict) -> dict:
    """Column of ``columns`` for each standard name (exact alias, else alias + unit suffix)."""
    keys = {c: _key(c) for c in columns}
    out = {}
    for std, names in aliases.items():
        for c, k in keys.items():
            if c in out.values():
                continue
            if k in names or any(k.startswith(n + "_") for n in names if len(n) > 2):
                out[std] = c
                break
    return out


def _table(source, sheet=None) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    p = Path(source)
    if p.suffix.lower() in (".xlsx", ".xls", ".xlsm", ".ods"):
        return pd.read_excel(p, sheet_name=sheet or 0)
    text = p.read_text(errors="replace")
    first = text.splitlines()[0] if text else ""
    sep = ";" if first.count(";") > first.count(",") else ("\t" if "\t" in first else ",")
    decimal = "," if sep == ";" else "."
    return pd.read_csv(p, sep=sep, decimal=decimal)


def _convert(df, col, cond, factor, offset, msg, log):
    v = pd.to_numeric(df[col], errors="coerce")
    if v.notna().any() and cond(v.dropna()):
        df[col] = v * factor + offset
        log.append(msg)
        warnings.warn(f"{col}: {msg}", stacklevel=3)
    else:
        df[col] = v


def _dates(t: pd.DataFrame) -> pd.DatetimeIndex:
    m = _match(t.columns, {"year": YEAR, "doy": DOY})
    if {"year", "doy"} <= set(m):
        return pd.DatetimeIndex(pd.to_datetime(t[m["year"]].astype(int).astype(str) + t[m["doy"]].astype(int)
                                               .astype(str).str.zfill(3), format="%Y%j"))
    m = _match(t.columns, {"year": YEAR, "month": MONTH, "day": DAY})
    if {"year", "month", "day"} <= set(m):
        return pd.DatetimeIndex(pd.to_datetime(dict(year=t[m["year"]], month=t[m["month"]], day=t[m["day"]])))
    m = _match(t.columns, {"date": DATE})
    if "date" in m:
        return pd.DatetimeIndex(pd.to_datetime(t[m["date"]], dayfirst=_dayfirst(t[m["date"]])))
    raise KeyError("no date: give a date column (date/data) or year + day of year or year, month, day")


def _dayfirst(s: pd.Series) -> bool:
    """True for text dates written day first (31/12/2020)."""
    v = s.dropna().astype(str)
    return bool(len(v)) and bool(v.str.match(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{4}").all())


# ---------------------------------------------------------------------------- weather
def read_weather(source, lat: float | None = None, lon: float | None = None, elev: float | None = None,
                 sheet=None) -> pd.DataFrame:
    """Daily weather from a spreadsheet into the cropemu standard table (see :mod:`cropemu.weather`).

    Needs a date (``date``/``data``, or year + day of year, or year, month, day) and radiation,
    maximum and minimum temperature and rain; humidity, wind and dew point are optional.
    Units: MJ/m²/d, °C, mm, %, m/s at 2 m. ``lat``, ``lon``, ``elev`` go to ``attrs`` (or come
    from columns of the same names)."""
    t = _table(source, sheet)
    idx = _dates(t)
    m = _match(t.columns, WEATHER)
    missing = [c for c in ("srad", "tmax", "tmin", "rain") if c not in m]
    if missing:
        raise KeyError(f"weather columns not found: {missing} (columns: {list(t.columns)})")
    out = pd.DataFrame({std: t[c].to_numpy() for std, c in m.items()}, index=idx)
    out.index.name = "date"
    log = []
    _convert(out, "srad", lambda v: v.median() > 1000, 1e-3, 0, "kJ/m²/d -> MJ/m²/d", log)
    _convert(out, "srad", lambda v: v.median() > 60, 0.0864, 0, "W/m² (daily mean) -> MJ/m²/d", log)
    for c in ("tmax", "tmin", "dewp"):
        if c in out:
            _convert(out, c, lambda v: v.median() > 150, 1, -273.15, "K -> °C", log)
    if "rhum" in out:
        _convert(out, "rhum", lambda v: v.max() <= 1.5, 100, 0, "fraction -> %", log)
    for c in ("rain", "wind"):
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out[~out.index.duplicated()].sort_index()
    site = _match(t.columns, {"lat": ["lat", "latitude"], "lon": ["lon", "long", "longitude"],
                              "elev": ["elev", "elevation", "altitude", "alt"]})
    val = lambda k, v: float(v) if v is not None else (float(t[site[k]].iloc[0]) if k in site else np.nan)
    out.attrs = {"lat": val("lat", lat), "lon": val("lon", lon), "elev": val("elev", elev),
                 "source": str(source) if not isinstance(source, pd.DataFrame) else "table",
                 "conversions": log}
    return out


# ---------------------------------------------------------------------------- soil
def _soil_table(t: pd.DataFrame) -> pd.DataFrame:
    m = _match(t.columns, SOIL)
    if "bottom" not in m:
        raise KeyError(f"soil: no layer depth (bottom/base/profundidade) in {list(t.columns)}")
    out = pd.DataFrame({std: t[c].to_numpy() for std, c in m.items()})
    for c in out:
        if c != "profile":
            out[c] = pd.to_numeric(out[c], errors="coerce")
    log = []
    for c in ("clay", "sand", "silt"):
        if c in out:
            _convert(out, c, lambda v: v.max() <= 1.0, 100, 0, "fraction -> %", log)
            _convert(out, c, lambda v: v.max() > 100, 0.1, 0, "g/kg -> %", log)
    if "soc" in out:
        _convert(out, "soc", lambda v: v.max() > 15, 0.1, 0, "g/kg -> %", log)
    if "om" in out:
        _convert(out, "om", lambda v: v.max() > 25, 0.1, 0, "g/kg -> %", log)
        if "soc" not in out or out["soc"].isna().all():
            out["soc"] = out["om"] / 1.724
            log.append("organic matter -> organic carbon (/1.724)")
        out = out.drop(columns="om")
    if "bdod" in out:
        _convert(out, "bdod", lambda v: v.median() > 100, 1e-3, 0, "kg/m³ -> g/cm³", log)
    for c in ("ll", "dul", "sat"):
        if c in out:
            _convert(out, c, lambda v: v.max() > 1.0, 0.01, 0, "% -> cm³/cm³", log)
    if "sand" not in out and {"clay", "silt"} <= set(out):
        out["sand"] = 100 - out["clay"] - out["silt"]
    if "silt" not in out and {"clay", "sand"} <= set(out):
        out["silt"] = 100 - out["clay"] - out["sand"]
    out.attrs["conversions"] = log
    return out


def _layers(p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values("bottom").reset_index(drop=True)
    if "top" not in p or p["top"].isna().all():
        p["top"] = p["bottom"].shift(1, fill_value=0.0)
    cols = ["top", "bottom"] + [c for c in p if c not in ("top", "bottom", "profile")]
    return p[cols]


def read_soils(source, sheet=None) -> dict[str, pd.DataFrame]:
    """Soil profiles from a spreadsheet, one row per layer, as ``{profile: table}``.

    Columns: a profile name (``profile``/``perfil``/``fazenda``...; optional when there is one
    profile), layer depths in cm (``top`` and ``bottom``, or only the bottom of each layer),
    ``clay``, ``sand`` (or ``silt``) in %, organic carbon (``soc``) or organic matter (``om``) in %,
    bulk density (``bdod``) in g/cm³ and, if measured, ``ll`` (1500 kPa), ``dul`` (field capacity)
    and ``sat`` in cm³/cm³. Without ``ll``/``dul`` the emulator computes them as in training."""
    t = _soil_table(_table(source, sheet))
    log = t.attrs.get("conversions", [])
    groups = t.groupby("profile", sort=False) if "profile" in t else [("profile", t)]
    out = {}
    for name, g in groups:
        p = _layers(g)
        p.attrs = {"profile": str(name), "conversions": log,
                   "source": str(source) if not isinstance(source, pd.DataFrame) else "table"}
        out[str(name)] = p
    return out


def read_soil(source, profile: str | None = None, sheet=None) -> pd.DataFrame:
    """One soil profile of a spreadsheet (see :func:`read_soils`); ``profile`` picks one of several."""
    soils = read_soils(source, sheet)
    if profile is None:
        if len(soils) > 1:
            raise ValueError(f"several profiles {list(soils)}: give profile=")
        return next(iter(soils.values()))
    return soils[str(profile)]


# ---------------------------------------------------------------------------- seasons
def read_seasons(source, sheet=None) -> pd.DataFrame:
    """Seasons (one row each) from a spreadsheet: site, field, sowing date, cultivar or maturity
    group, irrigated (yes/no, sim/não, 1/0) and, if observed, yield (kg/ha), flowering and
    maturity (dates or days after sowing). Observed dates become days after sowing
    (``obs_flowering``, ``obs_maturity``). Other columns are kept as they are."""
    t = _table(source, sheet)
    m = _match(t.columns, SEASONS)
    if "sowing" not in m:
        raise KeyError(f"seasons: no sowing date (sowing/semeadura) in {list(t.columns)}")
    out = t.rename(columns={c: std for std, c in m.items()})
    out["sowing"] = pd.to_datetime(out["sowing"], dayfirst=_dayfirst(out["sowing"]))
    if "irrigated" in out:
        out["irrigated"] = out["irrigated"].map(lambda v: _key(v) in TRUE if pd.notna(v) else False)
    else:
        out["irrigated"] = False
    for c in ("obs_flowering", "obs_maturity"):
        if c in out:
            v = out[c]
            num = pd.to_numeric(v, errors="coerce")
            if num.notna().sum() < v.notna().sum():                           # dates
                d = pd.to_datetime(v, dayfirst=_dayfirst(v), errors="coerce")
                out[c] = (d - out["sowing"]).dt.days
            else:
                out[c] = num
    if "obs_yield" in out:
        out["obs_yield"] = pd.to_numeric(out["obs_yield"], errors="coerce")
    return out


# ---------------------------------------------------------------------------- sites
SITES = {"site": SEASONS["site"] + ["name", "nome", "id"], "lat": ["lat", "latitude"],
         "lon": ["lon", "long", "longitude"], "elev": ["elev", "elevation", "altitude", "alt"]}


def read_sites(source, sheet=None) -> pd.DataFrame:
    """Sites (farms, stations) from a spreadsheet: name, latitude and longitude (decimal degrees,
    south and west negative) and elevation (m), indexed by name. Other columns are kept."""
    t = _table(source, sheet)
    m = _match(t.columns, SITES)
    missing = [c for c in ("site", "lat", "lon") if c not in m]
    if missing:
        raise KeyError(f"sites: columns not found: {missing} (columns: {list(t.columns)})")
    out = t.rename(columns={c: std for std, c in m.items()})
    for c in ("lat", "lon", "elev"):
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    bad = out[(out["lat"].abs() > 90) | (out["lon"].abs() > 180)]
    if len(bad):
        raise ValueError(f"sites with impossible coordinates: {list(bad['site'])}")
    out["site"] = out["site"].astype(str)
    return out.set_index("site")


# ---------------------------------------------------------------------------- templates
TEMPLATES = {
    "en": {
        "sites.csv": ["site", "lat", "lon", "elev (m)"],
        "weather.csv": ["date", "srad (MJ/m2/d)", "tmax (C)", "tmin (C)", "rain (mm)", "rhum (%)", "wind (m/s)"],
        "soil.csv": ["profile", "top (cm)", "bottom (cm)", "clay (%)", "sand (%)", "silt (%)", "soc (%)",
                     "bdod (g/cm3)", "ll (cm3/cm3)", "dul (cm3/cm3)"],
        "seasons.csv": ["site", "field", "sowing", "cultivar", "mg", "irrigated", "yield (kg/ha)",
                        "flowering", "maturity"],
    },
    "pt": {
        "locais.csv": ["fazenda", "lat", "lon", "altitude (m)"],
        "clima.csv": ["data", "radiacao (MJ/m2/d)", "tmax (C)", "tmin (C)", "chuva (mm)", "umidade (%)",
                      "vento (m/s)"],
        "solo.csv": ["perfil", "topo (cm)", "base (cm)", "argila (%)", "areia (%)", "silte (%)", "carbono (%)",
                     "densidade (g/cm3)", "pmp (cm3/cm3)", "cc (cm3/cm3)"],
        "safras.csv": ["fazenda", "talhao", "semeadura", "cultivar", "gm", "irrigado", "produtividade (kg/ha)",
                       "florescimento", "maturacao"],
    },
}
_EXAMPLE = {
    "sites": ["A", -24.5, -51.6, 600],
    "weather": ["2023-10-01", 22.5, 31.2, 18.4, 0.0, 65, 2.1],
    "soil": [["A", 0, 20, 55, 25, 20, 1.6, 1.20, "", ""], ["A", 20, 60, 60, 20, 20, 0.9, 1.25, "", ""],
             ["A", 60, 200, 62, 18, 20, 0.4, 1.30, "", ""]],
    "seasons": ["A", "T1", "2023-10-15", "my cultivar", 6.3, "no", 3650, "2023-12-10", "2024-02-20"],
}


def write_templates(folder, lang: str = "en") -> list[Path]:
    """Write example spreadsheets (CSV) with the expected columns and units to ``folder``:
    sites, weather, soil and seasons (``lang="pt"``: locais, clima, solo, safras, with Portuguese
    headers; latitude and longitude in decimal degrees, south and west negative).
    Replace the example rows with your data; empty cells are missing values."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for (name, cols), kind in zip(TEMPLATES[lang].items(), ("sites", "weather", "soil", "seasons")):
        rows = _EXAMPLE[kind] if kind == "soil" else [_EXAMPLE[kind]]
        if lang == "pt" and kind == "seasons":
            rows = [[*rows[0][:3], "minha cultivar", 6.3, "nao", *rows[0][6:]]]
        p = folder / name
        pd.DataFrame(rows, columns=cols).to_csv(p, index=False)
        paths.append(p)
    return paths
