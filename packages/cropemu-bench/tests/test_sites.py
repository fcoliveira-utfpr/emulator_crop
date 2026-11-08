from pathlib import Path

import pandas as pd
import pytest

from cropemu_bench.inputs.sites import (DSSAT_COEFFICIENTS, SITE_COLUMNS, ValidationError, load_coefficients,
                                        load_sites)

REVIEW = Path(__file__).parents[3] / "review"


def test_templates_match_validator():
    assert pd.read_csv(REVIEW / "sites_template.csv").columns.tolist() == SITE_COLUMNS
    cols = pd.read_csv(REVIEW / "coef_dssat_template.csv").columns.tolist()
    assert all(c in cols for c in DSSAT_COEFFICIENTS)


def _sites(tmp_path, rows):
    df = pd.DataFrame(rows, columns=SITE_COLUMNS)
    p = tmp_path / "sites.csv"
    df.to_csv(p, index=False)
    return p


def _row(site_id, lat, lon, **kw):
    r = dict.fromkeys(SITE_COLUMNS)
    r.update(site_id=site_id, country="BR", lat=lat, lon=lon, coord_precision="exact", source_type="paper",
             source_ref="10.0000/example", observed="phenology|yield")
    r.update(kw)
    return r


def test_load_valid_sites(tmp_path):
    df = load_sites(_sites(tmp_path, [_row("A", -23.2, -51.2), _row("B", 40.1, -88.2, water_regime="rainfed")]))
    assert df["observed"].iloc[0] == ["phenology", "yield"]


def test_sites_problems_are_all_reported(tmp_path):
    rows = [_row("A", -23.2, -51.2), _row("A", 95, -51.2), _row("C", -23.2001, -51.2001),
            _row("D", 10, 10, coord_precision="approx", observed="yield|grain")]
    with pytest.raises(ValidationError) as e:
        load_sites(_sites(tmp_path, rows))
    msg = str(e.value)
    for part in ("duplicated site_id", "lat not a number", "coord_precision must be", "unknown values ['grain']",
                 "within 1 km"):
        assert part in msg


def test_coefficients(tmp_path):
    sites = load_sites(_sites(tmp_path, [_row("A", -23.2, -51.2)]))
    cols = pd.read_csv(REVIEW / "coef_dssat_template.csv").columns
    row = dict.fromkeys(cols)
    row.update(coef_id="c1", source_ref="10.0000/x", model_version="4.8", site_ids="A|Z", CSDL=12.5, PPSEN=0.3)
    p = tmp_path / "coef.csv"
    pd.DataFrame([row]).to_csv(p, index=False)
    with pytest.raises(ValidationError, match=r"not in sites table \['Z'\]"):
        load_coefficients(p, "dssat", sites)
    row["site_ids"] = "A"
    pd.DataFrame([row]).to_csv(p, index=False)
    df = load_coefficients(p, "dssat", sites)
    assert df["CSDL"].iloc[0] == 12.5 and df["site_ids"].iloc[0] == ["A"]
