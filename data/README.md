# Real study-area data

`norfolk_elizabeth_river_dem.tif` is a small real bare-earth elevation subset
covering the Elizabeth River and Norfolk, Virginia.

- Source: USGS National Map 3D Elevation Program (3DEP)
- Extent: `[-76.31, 36.80, -76.23, 36.88]` in WGS 84
- Output CRS: UTM Zone 18N (`EPSG:32618`)
- Raster size: 900 x 900 cells
- Approximate output spacing: 9-10 meters
- Vertical datum: not established by the current ImageServer export provenance
- Usage: public domain; USGS states that 3DEP products are free of charge and
  without use restrictions

The exact service request and raster statistics are recorded in
`norfolk_elizabeth_river_dem.json`. Regenerate both files with:

```powershell
python scripts/download_real_dem.py
```

The raster is a terrain input for a portfolio demonstration. It does not
contain observed flood depths or a calibrated water surface.
