# Data quality and interpretation

## Norfolk case study

The real case study covers the tidal Elizabeth River and Norfolk, Virginia. Its
bare-earth DEM is downloaded from the USGS 3D Elevation Program and clipped to
a small UTM Zone 18N grid. Source URL, access date, bounds, CRS, and observed
elevation range are retained in `data/norfolk_elizabeth_river_dem.json`.
The current source record does not establish a vertical datum, so reports keep
`vertical_datum` as `null` rather than inferring one.

Synthetic rasters remain the basis of automated tests so CI does not depend on
external data availability.

## Bathtub-model limitations

GeoFlood calculates:

```text
depth = max(water_surface_elevation - terrain_elevation, 0)
```

This simplified bathtub method does not test whether a low cell is connected to
the coast or river. It also does not model flow, rainfall-runoff, drainage,
levees, velocity, or time.

## Vertical datum compatibility

The water-surface elevation and DEM must share vertical units and a compatible
vertical datum. A `2 m` water level referenced to one datum cannot be safely
subtracted from terrain referenced to another. Horizontal CRS metadata does not
by itself prove that vertical datums match.

## Negative elevations and water cells

The Norfolk subset contains elevations below `-1 m`. These may represent valid
low terrain, interpolation over water, bathymetry, or datum effects. Because
the calculation is subtraction, a DEM value of `-7.21 m` produces a depth near
`9.21 m` under a `2 m` water surface.

GeoFlood reports warnings when:

- valid DEM elevations fall below `-1 m`;
- maximum depth exceeds the scenario water level;
- CRS metadata are missing;
- nodata metadata are missing.

Warnings are emitted in both CLI output and the JSON report.

## Report provenance and derived quantities

When a same-stem provenance JSON exists beside a DEM, GeoFlood includes its
location name, source, source URL, download date, and vertical datum in the
scenario report. A different provenance file can be supplied with
`--provenance`.

Reports include projected bounds, WGS 84 longitude/latitude bounds, total area,
flooded area in square meters, square kilometers, and acres, plus estimated
flood volume:

```text
estimated_flood_volume_m3 =
    mean_depth_flooded_cells_m * flooded_area_m2
```

This is a geometric raster summary for a simplified bathtub scenario. It is not
a hydrodynamic storage, flow, or discharge calculation.

## Land-mask workflow

For a land-only screening product, preprocess the DEM using an authoritative,
reviewed land polygon:

1. Reproject the polygon to the DEM CRS.
2. Raster-mask cells outside the land polygon to the DEM nodata value.
3. Inspect shoreline alignment at the raster resolution.
4. Run GeoFlood on the masked DEM.
5. Preserve the mask source, date, CRS, and processing command as provenance.

Do not automatically discard all negative terrain: legitimate subsided or
below-sea-level land exists. Masking should be based on a land/water dataset,
not an elevation threshold alone.
