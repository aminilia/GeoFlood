# GeoFlood CI/CD Platform

GeoFlood is a compact, production-style geospatial processing platform. It
demonstrates how a transparent scientific calculation can be packaged,
validated, tested, containerized, scanned, and delivered as reproducible
artifacts.

## Featured study area

The portfolio demo uses a real USGS 3DEP bare-earth DEM covering the Elizabeth
River and Norfolk, Virginia. The clipped area spans approximately 8 by 9
kilometers and includes tidal shoreline, river branches, and low-relief urban
terrain. The download script records its source URL, extent, CRS, access date,
and elevation range in a JSON provenance file.

Synthetic data are retained for automated tests and CI reliability.

The Norfolk source raster includes negative coastal/water elevations. GeoFlood
therefore emits visible warnings when modeled depth exceeds the scenario water
level. See [data quality and interpretation](data_quality.md) for vertical
datum and land-mask guidance.

## Processing model

For each valid DEM cell:

```text
flood_depth = max(water_level - terrain_elevation, 0)
```

The output retains the source grid, coordinate reference system, affine
transform, and nodata convention. A positive value means the constant
water-surface elevation is above the terrain cell.

!!! warning "Model scope"
    This is a static inundation screening model. It does not model flow
    connectivity, rainfall-runoff, velocity, levee failure, uncertainty, or
    real-time conditions and must not be treated as an operational forecast.
    Water levels and DEM elevations must also use compatible vertical datums.

## Interfaces

- `geoflood run` supports repeatable local and batch processing.
- `POST /run-flood-scenario` supports path-based processing in a service or
  mounted-container environment.
- Optional zone polygons produce CSV summaries suitable for reporting.

Start with the [architecture](architecture.md), then see the
[CI/CD design](ci_cd.md) and [API reference](api.md).
