# Training labels (v2 Gate 1)

The Phase 2 model is trained on the **FEMA National Flood Hazard Layer (NFHL)
flood-zone class** of each DEM cell. It is therefore a *flood-zone emulator*:
its output may be described as the probability that the effective FIRM maps a
cell in the Special Flood Hazard Area (SFHA), with calibration measured on
spatially held-out data. It is not a probability of flooding.

## Getting the data

```bash
python scripts/download_nfhl.py          # needs internet; standard library only
dvc repro labels_norfolk
```

The downloader queries FEMA's public NFHL service for the DEM's bounding box
and writes `data/nfhl/norfolk_nfhl.geojson` (polygons, EPSG:4326) and
`data/nfhl/norfolk_nfhl.json` (service, access time, DFIRM IDs, FIRM panel
effective dates, zone counts).

## Classes

| Code | Class | NFHL zones | Binary `sfha` |
| --- | --- | --- | --- |
| 6 | V zone | V, VE | 1 |
| 5 | A zone | A, AE, AH, AO, AR, A99, A1-30 | 1 |
| 4 | Shaded X | X with 0.2% annual chance, levee, or 1% shallow subtype | 0 |
| 3 | Unshaded X | X, area of minimal flood hazard | 0 |
| 2 | D | Undetermined | nodata |
| 1 | Open water | OPEN WATER | nodata |
| 0 | Unmapped | No polygon at the cell centre | nodata |

Each cell takes the class of the polygon covering its centre; overlaps resolve
to the more hazardous class. `labels.tif` holds the class in band 1 and the
binary SFHA label in band 2 (255 = excluded).

## Leakage guards

Model features come only from terrain, hydrology, and land surface. The
following NFHL attributes encode the answer and are never features:
`STATIC_BFE`, `DEPTH`, `SFHA_TF`, `ZONE_SUBTY`, `DFIRM_ID`, `SOURCE_CIT`.
Open-water cells (`is_water` feature) are also excluded from training and
scoring.

## Norfolk study box (NFHL queried 2026-09-28)

- 901 flood-hazard polygons from DFIRMs 510034, 510104, and 515529
- FIRM panels effective between 2009-05-04 and 2017-02-17
- NFHL vertical datum: NAVD88
- Polygon counts: AE 85, AH 3, VE 3, shaded X 456, unshaded X 354

## Validation rules

- Spatial blocks larger than typical zone polygons, plus leave-one-DFIRM-out
- Scores reported with and without a 2-cell buffer around zone boundaries
- Baselines: elevation threshold and HAND threshold tuned on training folds
- A second region as the transfer test
