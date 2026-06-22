"""Polygon summaries for generated flood-depth rasters."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.mask import mask


def calculate_zonal_stats(raster_path: Path, zones_path: Path) -> pd.DataFrame:
    """Calculate flood-depth statistics for each polygon feature.

    Zones are reprojected to the raster CRS. Pixels outside a polygon and nodata
    pixels are excluded from the reported statistics.
    """
    zones = gpd.read_file(zones_path)
    if zones.empty:
        raise ValueError("Zones dataset contains no features")

    records: list[dict[str, int | float | str]] = []
    with rasterio.open(raster_path) as dataset:
        if dataset.crs is None:
            raise ValueError("Raster must have a CRS for zonal statistics")
        if zones.crs is None:
            raise ValueError("Zones must have a CRS for zonal statistics")
        projected = zones.to_crs(dataset.crs)

        for index, row in projected.iterrows():
            clipped, _ = mask(dataset, [row.geometry], crop=True, filled=False)
            values = clipped[0].compressed()
            flooded = values[values > 0]
            records.append(
                {
                    "zone_id": str(row.get("zone_id", index)),
                    "valid_cell_count": int(values.size),
                    "flooded_cell_count": int(flooded.size),
                    "mean_depth": float(values.mean()) if values.size else 0.0,
                    "max_depth": float(values.max()) if values.size else 0.0,
                    "flooded_fraction": (
                        float(flooded.size / values.size) if values.size else 0.0
                    ),
                }
            )
    return pd.DataFrame.from_records(records)


def write_zonal_stats(raster_path: Path, zones_path: Path, output_csv: Path) -> Path:
    """Calculate polygon summaries and write them to CSV."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    calculate_zonal_stats(raster_path, zones_path).to_csv(output_csv, index=False)
    return output_csv
