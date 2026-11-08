"""Experiment sites and published cultivar coefficients from the systematic review (review/)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..models.dssat.cultivar import COEFFICIENTS as DSSAT_COEFFICIENTS

SITE_COLUMNS = ["site_id", "name", "country", "lat", "lon", "elev_m", "coord_precision", "source_type",
                "source_ref", "years", "n_seasons", "water_regime", "observed", "maturity_groups",
                "data_public", "data_url", "notes"]
SITE_REQUIRED = ["site_id", "country", "lat", "lon", "coord_precision", "source_type", "source_ref", "observed"]
ENUMS = {"coord_precision": {"exact", "town", "region"},
         "source_type": {"paper", "network", "database"},
         "water_regime": {"rainfed", "irrigated", "both"},
         "data_public": {"yes", "no", "on_request"}}
OBSERVED = {"phenology", "yield", "biomass", "lai", "soil_water", "soil_n", "plant_n"}

COEF_COMMON = ["coef_id", "source_ref", "model_version", "cultivar", "maturity_group", "site_ids",
               "calibration_data", "n_seasons_cal", "n_seasons_eval"]
#: AquaCrop columns are provisional: align them with the v7 crop file when the adapter exists.
AQUACROP_COEFFICIENTS = ["time_mode", "Tbase", "Tupper", "emergence", "max_rooting", "senescence", "maturity",
                         "flowering", "flowering_duration", "CCx", "CGC", "CDC", "CC0", "Zmin", "Zmax", "WP",
                         "HI0", "p_upper_expansion", "p_lower_expansion", "p_upper_stomata",
                         "p_upper_senescence"]


class ValidationError(ValueError):
    pass


def _split(s) -> list[str]:
    return [] if pd.isna(s) else [x.strip() for x in str(s).split("|") if x.strip()]


def load_sites(path) -> pd.DataFrame:
    """Read and validate ``sites.csv``. Raises :class:`ValidationError` listing every problem."""
    df = pd.read_csv(path, dtype={"site_id": str})
    problems = []
    missing = [c for c in SITE_COLUMNS if c not in df]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    for c in SITE_REQUIRED:
        bad = df.index[df[c].isna()].tolist()
        if bad:
            problems.append(f"{c} empty in rows {bad}")
    dup = df["site_id"][df["site_id"].duplicated()].tolist()
    if dup:
        problems.append(f"duplicated site_id: {dup}")
    for c, lo, hi in (("lat", -90, 90), ("lon", -180, 180)):
        v = pd.to_numeric(df[c], errors="coerce")
        bad = df.index[v.isna() | (v < lo) | (v > hi)].tolist()
        if bad:
            problems.append(f"{c} not a number in [{lo}, {hi}] in rows {bad}")
    for c, allowed in ENUMS.items():
        bad = df.index[df[c].notna() & ~df[c].isin(allowed)].tolist()
        if bad:
            problems.append(f"{c} must be one of {sorted(allowed)}; rows {bad}")
    for i, s in df["observed"].items():
        unknown = set(_split(s)) - OBSERVED
        if unknown:
            problems.append(f"observed has unknown values {sorted(unknown)} in row {i}")
    near = _near_duplicates(df)
    if near:
        problems.append(f"different site_id within 1 km (same site?): {near}")
    if problems:
        raise ValidationError("; ".join(problems))
    df["observed"] = df["observed"].map(_split)
    return df


def _near_duplicates(df: pd.DataFrame, km: float = 1.0) -> list[tuple[str, str]]:
    lat = np.radians(pd.to_numeric(df["lat"], errors="coerce").to_numpy())
    lon = np.radians(pd.to_numeric(df["lon"], errors="coerce").to_numpy())
    ids = df["site_id"].tolist()
    pairs = []
    for i in range(len(df)):
        d = 6371 * 2 * np.arcsin(np.sqrt(np.sin((lat[i + 1:] - lat[i]) / 2) ** 2
                                         + np.cos(lat[i]) * np.cos(lat[i + 1:]) * np.sin((lon[i + 1:] - lon[i]) / 2) ** 2))
        pairs += [(ids[i], ids[i + 1 + j]) for j in np.flatnonzero(d < km)]
    return pairs


def load_coefficients(path, model: str, sites: pd.DataFrame | None = None) -> pd.DataFrame:
    """Read and validate ``coef_dssat.csv`` or ``coef_aquacrop.csv``.

    With ``sites``, also checks that every ``site_ids`` entry exists in the sites table.
    """
    coefs = {"dssat": DSSAT_COEFFICIENTS, "aquacrop": AQUACROP_COEFFICIENTS}[model]
    df = pd.read_csv(path, dtype={"coef_id": str})
    missing = [c for c in COEF_COMMON + coefs if c not in df]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    problems = []
    dup = df["coef_id"][df["coef_id"].duplicated()].tolist()
    if dup:
        problems.append(f"duplicated coef_id: {dup}")
    for c in ("coef_id", "source_ref", "model_version"):
        bad = df.index[df[c].isna()].tolist()
        if bad:
            problems.append(f"{c} empty in rows {bad}")
    numeric = [c for c in coefs if c != "time_mode"]
    for c in numeric:
        v = pd.to_numeric(df[c], errors="coerce")
        bad = df.index[df[c].notna() & v.isna()].tolist()
        if bad:
            problems.append(f"{c} not numeric in rows {bad}")
    if sites is not None:
        known = set(sites["site_id"])
        for i, s in df["site_ids"].items():
            unknown = set(_split(s)) - known
            if unknown:
                problems.append(f"row {i}: site_ids not in sites table {sorted(unknown)}")
    if problems:
        raise ValidationError("; ".join(problems))
    df[numeric] = df[numeric].apply(pd.to_numeric)
    df["site_ids"] = df["site_ids"].map(_split)
    return df
