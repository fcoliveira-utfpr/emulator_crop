# review

Systematic review (phase 0a): published soybean experiment sites and calibrated
cultivar coefficients. The protocol is in [protocolo_revisao.md](protocolo_revisao.md)
(Portuguese).

| File | Content |
|---|---|
| `sites_template.csv` | Columns of `sites.csv` (one row per experiment site). |
| `coef_dssat_template.csv` | Columns of `coef_dssat.csv` (one row per calibrated CROPGRO-Soybean cultivar). |
| `coef_aquacrop_template.csv` | Columns of `coef_aquacrop.csv` (one row per calibrated AquaCrop soybean). |

Validate the filled files with:

```python
from cropemu_bench.inputs.sites import load_sites, load_coefficients
sites = load_sites("review/sites.csv")
dssat = load_coefficients("review/coef_dssat.csv", model="dssat")
```

## Column conventions (sites)

| Column | Values |
|---|---|
| `lat`, `lon` | decimal degrees (WGS84) |
| `coord_precision` | `exact` (from the source), `town` (geocoded municipality/station), `region` |
| `source_type` | `paper`, `network`, `database` |
| `source_ref` | DOI or URL; several separated by `|` |
| `years` | `2015-2017` or `2015|2018` |
| `water_regime` | `rainfed`, `irrigated`, `both` |
| `observed` | `|`-separated: `phenology`, `yield`, `biomass`, `lai`, `soil_water`, `soil_n`, `plant_n` |
| `data_public` | `yes`, `no`, `on_request` |
