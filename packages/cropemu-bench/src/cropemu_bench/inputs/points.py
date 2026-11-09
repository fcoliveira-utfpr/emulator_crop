"""Global simulation points on the 0.5° grid of NASA POWER and GGCMI.

Points = experiment sites (from the systematic review) + fill points sampled by
stratum (Köppen-Geiger class x latitude band), so the climate space is covered
where there are no experiments. Data (all open, no registration):

- soybean and other crops' harvested area: GAEZ+ 2015 (Grogan et al. 2022, Sci. Data;
  Harvard Dataverse 10.7910/DVN/KAGRFI, CC0), 5 arc-minutes, 1000 ha per cell;
- Köppen-Geiger 1991-2020: Beck et al. 2023 (Sci. Data; figshare 10.6084/m9.figshare.21789074,
  CC BY 4.0), 0.5° map.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .download import cache_dir, fetch_file

GAEZ_URL = "https://dataverse.harvard.edu/api/access/datafile/{id}"
GAEZ_FILES = {  # crop: (Dataverse file id, md5) of GAEZAct2015_HarvArea_<crop>_Total.tif
    "Soybean": (3862261, "e4eb439254daff70f5469b7c59ab3170"),
    "Maize": (3862276, "e98366fa6cf9ae6019d746b54a1bfc9c"),
    "Wheat": (3862258, "6c65edf19b26b75341dc252c59e76125"),
    "Sorghum": (3862262, "8481b7c1695ae8040b696c44658f64ae"),
    "Millet": (3862266, "8f4c9f87b7c75212edf45cc77cee8d30"),
    "Cotton": (3862271, "e959b69487f75648f4c50254947a1042"),
    "Groundnut": (3862256, "92c1693340cb16cd23be33c09cd9d45d"),
    "Pulses": (3862273, "6cfb0755531f470d75677fd135520694"),
    "Sunflower": (3862257, "e687c69f7ff877f7359e94dc10bd0f01"),
}
EXPANSION_CROPS = ("Maize", "Wheat", "Sorghum", "Millet", "Cotton", "Groundnut", "Pulses", "Sunflower")
KOPPEN_URL = "https://ndownloader.figshare.com/files/61012822"
KOPPEN_MD5 = "7fc2f5a15d4f5fe0ce59c9a9b502aa09"
KOPPEN_FILE = "1991_2020/koppen_geiger_0p5.tif"
KOPPEN_CLASSES = ["Af", "Am", "Aw", "BWh", "BWk", "BSh", "BSk", "Csa", "Csb", "Csc", "Cwa", "Cwb", "Cwc",
                  "Cfa", "Cfb", "Cfc", "Dsa", "Dsb", "Dsc", "Dsd", "Dwa", "Dwb", "Dwc", "Dwd", "Dfa", "Dfb",
                  "Dfc", "Dfd", "ET", "EF"]

#: 0.5° grid (cell centres), north to south and west to east, like GGCMI and the maps.
LATS = np.arange(89.75, -90, -0.5)
LONS = np.arange(-179.75, 180, 0.5)


# ---------------------------------------------------------------------------- data
def _read_tif(path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as src:
        return src.read(1, masked=True).astype("float64").filled(np.nan)


def harvested_area_05(crop: str) -> np.ndarray:
    """Harvested area (ha) of a GAEZ+ 2015 crop on the 0.5° grid (sum of 6 x 6 cells)."""
    fid, md5sum = GAEZ_FILES[crop]
    path = fetch_file(GAEZ_URL.format(id=fid), cache_dir("gaez") / f"GAEZAct2015_HarvArea_{crop}_Total.tif", md5sum)
    a = _read_tif(path)                                            # 2160 x 4320, 1000 ha
    if a.shape != (2160, 4320):
        raise ValueError(f"unexpected GAEZ+ grid {a.shape}")
    return np.nansum(a.reshape(360, 6, 720, 6), axis=(1, 3)) * 1000


def koppen_05() -> np.ndarray:
    """Köppen-Geiger class (1-30, 0 = water) of 1991-2020 on the 0.5° grid."""
    z = fetch_file(KOPPEN_URL, cache_dir("koppen") / "koppen_geiger_tif.zip", KOPPEN_MD5, timeout=900)
    out = cache_dir("koppen") / KOPPEN_FILE
    if not out.exists():
        with zipfile.ZipFile(z) as f:
            f.extract(KOPPEN_FILE, cache_dir("koppen"))
    k = _read_tif(out)
    if k.shape != (360, 720):
        raise ValueError(f"unexpected Köppen grid {k.shape}")
    return np.nan_to_num(k, nan=0).astype(int)


def grid_table(expansion_crops=EXPANSION_CROPS) -> pd.DataFrame:
    """One row per land cell of the 0.5° grid: soybean area, area of other field crops, Köppen."""
    soy = harvested_area_05("Soybean")
    other = sum(harvested_area_05(c) for c in expansion_crops)
    kop = koppen_05()
    lat2, lon2 = np.meshgrid(LATS, LONS, indexing="ij")
    df = pd.DataFrame({"lat": lat2.ravel(), "lon": lon2.ravel(), "soy_ha": soy.ravel(),
                       "other_ha": other.ravel(), "koppen_id": kop.ravel()})
    df = df[df["koppen_id"] > 0].reset_index(drop=True)
    df["koppen"] = [KOPPEN_CLASSES[i - 1] for i in df["koppen_id"]]
    return df


# ---------------------------------------------------------------------------- design
def cell_of(lat, lon) -> tuple[np.ndarray, np.ndarray]:
    """Centre of the 0.5° cell containing each point."""
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    return np.floor(lat * 2) / 2 + 0.25, np.floor(lon * 2) / 2 + 0.25


def add_strata(df: pd.DataFrame, lat_band: float = 10.0, block: float = 5.0) -> pd.DataFrame:
    """Add ``stratum`` (Köppen class x latitude band) and ``block`` (spatial block of
    ``block`` x ``block`` degrees, used to keep whole blocks out in validation)."""
    out = df.copy()
    band = np.floor(out["lat"] / lat_band) * lat_band
    out["stratum"] = out["koppen"] + "|" + band.astype(int).astype(str)
    out["block"] = ((np.floor(out["lat"] / block)).astype(int).astype(str) + "_"
                    + (np.floor(out["lon"] / block)).astype(int).astype(str))
    return out


def allocate(weights: pd.Series, n: int, minimum: int, capacity: pd.Series) -> pd.Series:
    """Integer allocation of ``n`` points over strata ∝ ``weights``, with at least
    ``minimum`` per stratum and at most ``capacity`` (largest-remainder method)."""
    w = weights.clip(lower=0).astype(float)
    cap = capacity.reindex(w.index).fillna(0).astype(int)
    alloc = np.minimum(cap, minimum)
    if alloc.sum() > n:
        raise ValueError(f"{alloc.sum()} points needed for the minimum per stratum, only {n} available")
    while alloc.sum() < n:
        free = cap > alloc
        if not free.any():
            break
        rest = n - alloc.sum()
        share = w[free] / w[free].sum() * rest if w[free].sum() > 0 else pd.Series(rest / free.sum(), w[free].index)
        add = np.minimum(np.floor(share).astype(int), cap[free] - alloc[free])
        if add.sum() == 0:                                         # hand out remainders one by one
            order = (share - np.floor(share)).sort_values(ascending=False).index
            add = pd.Series(0, index=share.index)
            add[order[:rest]] = 1
            add = np.minimum(add, cap[free] - alloc[free])
        alloc[free] += add
    return alloc.astype(int)


def allocate_fill(weights: pd.Series, n: int, minimum: int, capacity: pd.Series,
                  existing: pd.Series | None = None) -> pd.Series:
    """Exactly ``n`` new points over strata, given points that already exist (e.g. sites).

    Each stratum first gets enough to reach ``minimum`` (counting existing points);
    then each new point goes to the stratum furthest below its share ∝ ``weights``
    of the final total. Never more than ``capacity`` new points per stratum.
    """
    w = weights.clip(lower=0).astype(float)
    idx = w.index
    share = w / w.sum() if w.sum() > 0 else pd.Series(1 / len(w), idx)
    have = (existing if existing is not None else pd.Series(dtype=float)).reindex(idx).fillna(0).to_numpy()
    cap = capacity.reindex(idx).fillna(0).to_numpy().astype(int)
    fill = np.minimum(np.clip(minimum - have, 0, None), cap).astype(int)
    if fill.sum() > n:
        raise ValueError(f"{fill.sum()} points needed for the minimum per stratum, only {n} available")
    target = share.to_numpy() * (n + have.sum())
    while fill.sum() < n:
        deficit = np.where(fill < cap, target - have - fill, -np.inf)
        if np.isneginf(deficit).all():
            break
        fill[int(np.argmax(deficit))] += 1
    return pd.Series(fill, idx)


@dataclass
class PointDesign:
    n_total: int = 2000
    expansion_share: float = 0.15       # fraction of fill points in field-crop areas without soybean
    min_soy_ha: float = 500.0           # a cell "has soybean" above this harvested area
    min_other_ha: float = 5000.0        # a cell is a field-crop area above this (expansion candidates)
    min_per_stratum: int = 2
    lat_band: float = 10.0
    block: float = 5.0
    exclude_koppen: tuple = ("ET", "EF")   # polar: no soybean (mountain cells classified so at 0.5°)
    seed: int = 20261108


def sample_points(grid: pd.DataFrame, design: PointDesign = PointDesign(),
                  sites: pd.DataFrame | None = None) -> pd.DataFrame:
    """Experiment sites + fill points.

    ``grid`` comes from :func:`grid_table` (or has the same columns). ``sites`` (from
    ``load_sites``) keep their coordinates; their cell's strata count towards the
    allocation, so strata already covered by sites get fewer fill points.
    Returns ``id``, ``lat``, ``lon``, ``kind`` (site / soy / expansion), ``koppen``,
    ``stratum``, ``block``, ``soy_ha``.
    """
    rng = np.random.default_rng(design.seed)
    g = add_strata(grid, design.lat_band, design.block)
    fill_pool = g[~g["koppen"].isin(design.exclude_koppen)]
    soy = fill_pool[fill_pool["soy_ha"] >= design.min_soy_ha]
    exp_ = fill_pool[(fill_pool["soy_ha"] < design.min_soy_ha) & (fill_pool["other_ha"] >= design.min_other_ha)]

    rows = []
    taken = set()
    if sites is not None and len(sites):
        clat, clon = cell_of(sites["lat"], sites["lon"])
        info = g.set_index(["lat", "lon"])
        for s, la, lo in zip(sites.itertuples(), clat, clon):
            cell = info.loc[(la, lo)] if (la, lo) in info.index else None
            rows.append({"id": f"site:{s.site_id}", "lat": s.lat, "lon": s.lon, "kind": "site",
                         "koppen": cell["koppen"] if cell is not None else None,
                         "stratum": cell["stratum"] if cell is not None else None,
                         "block": cell["block"] if cell is not None else None,
                         "soy_ha": cell["soy_ha"] if cell is not None else np.nan})
            taken.add((la, lo))
    site_counts = pd.Series([r["stratum"] for r in rows if r["stratum"]], dtype=object).value_counts()
    n_fill = max(design.n_total - len(rows), 0)
    n_exp = int(round(n_fill * design.expansion_share))

    def draw(pool: pd.DataFrame, n: int, kind: str, weight_col: str | None, prior: pd.Series):
        pool = pool[[(a, b) not in taken for a, b in zip(pool["lat"], pool["lon"])]]
        if n <= 0 or pool.empty:
            return
        by = pool.groupby("stratum")
        weights = np.sqrt(by[weight_col].sum()) if weight_col else by.size().astype(float)
        # with few points and many strata, lower the minimum so that it fits
        minimum = min(design.min_per_stratum, n // len(weights))
        need = allocate_fill(weights, n, minimum, by.size(), prior)
        for st, k in need.items():
            if k == 0:
                continue
            cells = by.get_group(st)
            p = cells[weight_col].to_numpy() if weight_col else np.ones(len(cells))
            p = p / p.sum() if p.sum() > 0 else None
            pick = rng.choice(len(cells), size=min(k, len(cells)), replace=False, p=p)
            for c in cells.iloc[pick].itertuples():
                rows.append({"id": f"{kind}:{c.lat:+.2f}_{c.lon:+.2f}", "lat": c.lat, "lon": c.lon, "kind": kind,
                             "koppen": c.koppen, "stratum": c.stratum, "block": c.block, "soy_ha": c.soy_ha})
                taken.add((c.lat, c.lon))

    draw(soy, n_fill - n_exp, "soy", "soy_ha", site_counts)
    draw(exp_, n_exp, "expansion", "other_ha", pd.Series(dtype=int))
    return pd.DataFrame(rows)
