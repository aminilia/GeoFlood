# Feature pipeline (v2 Phase 1)

GeoFlood v2 turns a DEM into a per-cell feature table for flood-risk
modelling. One command rebuilds it from the committed Norfolk DEM:

```bash
pip install -e ".[dev,pipeline]"
dvc repro          # runs the features_norfolk stage defined in dvc.yaml
```

or directly:

```bash
geoflood features \
  --dem data/norfolk_elizabeth_river_dem.tif \
  --output-dir outputs/features/norfolk \
  --water-threshold 0.0 \
  --scenario-level 1.0 --scenario-level 2.0
```

Parameters live in `params.yaml`; DVC records input, code, and parameter hashes
in `dvc.lock`, so a changed feature function or parameter invalidates the
stage.

## Products

| File | Contents |
| --- | --- |
| `features.tif` | Cloud-Optimized GeoTIFF, one band per feature, band descriptions = feature names, source CRS and transform |
| `features.parquet` | GeoParquet, one row per valid cell: centre point, `row`, `col`, every feature |
| `features.json` | CRS, vertical datum, configuration, per-feature description and summary statistics, warnings, source provenance (tracked in git as a DVC metric) |

## Features

| Feature | Method |
| --- | --- |
| `elevation` | DEM value |
| `elev_above_reference` | Elevation minus `reference_level` (intended: MHHW in the DEM datum) |
| `slope_deg` | Central-difference slope |
| `local_relief` | Max minus min elevation in a 5 x 5 window |
| `log_flow_accumulation` | `ln(1 + upstream cells)` from D8 routing on a priority-flood-filled DEM |
| `twi` | `ln(a / tan(beta))`, with `tan(beta)` floored at 0.001 |
| `hand` | Height above nearest drainage along the D8 path; drainage = open water or channels above `stream_threshold` upstream cells |
| `distance_to_water` | Euclidean distance to the open-water mask |
| `is_water` | Open-water mask (`elevation <= water_threshold`) |
| `connected_depth_<level>m` | Depth below a static water level on land cells hydraulically connected to open water |

## Connected bathtub vs. v1 bathtub

v1 floods every cell below the water level. The connected variant floods a
cell only if an 8-connected path of below-level cells links it to open water.
On the Norfolk subset with open water at or below 0 m (vertical datum still
unknown), the land area flooded at a static 2.0 m level falls from about
11.0 km² (bathtub) to about 9.1 km² (connected), and at 1.0 m from about
4.2 km² to 3.8 km². The removed cells are low inland areas that a static
coastal water level cannot reach without flowing over higher ground.

Both remain static screening products. Neither models flow, drainage
infrastructure, rainfall, or timing.

## Known limitations

- **Vertical datum.** The Norfolk DEM's vertical datum is not established by
  its export provenance. `features.json` records `null` and warns until a datum
  is declared with `--vertical-datum`. Converting MHHW at Sewells Point to the
  DEM datum (VDatum) is the next pipeline step.
- **Open-water mask.** Derived from an elevation threshold. 3DEP flattens open
  water in this subset to about -0.67 m, so 0 m separates it cleanly here; a
  reviewed shoreline polygon should replace the threshold.
- **Edge effects.** Cells that drain off the raster edge before reaching a
  channel have `hand = NaN` (about 1.7 % of Norfolk cells).
- **Scale.** Routing uses a pure-Python priority queue: about 10 s for the
  900 x 900 Norfolk grid. Tiles from 1 m lidar need blocking or a compiled
  backend.

## References

- Barnes, R., Lehman, C., Mulla, D. (2014). Priority-flood: An optimal
  depression-filling and watershed-labeling algorithm for digital elevation
  models. *Computers & Geosciences* 62, 117-127.
- Nobre, A. D., et al. (2011). Height Above the Nearest Drainage - a
  hydrologically relevant new terrain model. *Journal of Hydrology* 404, 13-29.
