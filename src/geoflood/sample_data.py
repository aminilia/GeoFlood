"""Deterministic synthetic geospatial data generation for tests and demos."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box


def generate_sample_data(data_dir: Path) -> tuple[Path, Path]:
    """Create a 10x10 DEM and two polygon zones in EPSG:32618.

    Args:
        data_dir: Directory where the GeoTIFF and GeoJSON files are written.

    Returns:
        Paths to the generated DEM and polygon zones, respectively.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    dem_path = data_dir / "sample_dem.tif"
    zones_path = data_dir / "sample_zones.geojson"

    terrain = np.linspace(0.0, 6.0, 100, dtype=np.float32).reshape(10, 10)
    terrain[0, 0] = -9999.0
    transform = from_origin(500_000.0, 4_500_000.0, 10.0, 10.0)
    with rasterio.open(
        dem_path,
        "w",
        driver="GTiff",
        height=terrain.shape[0],
        width=terrain.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:32618",
        transform=transform,
        nodata=-9999.0,
        compress="deflate",
    ) as dataset:
        dataset.write(terrain, 1)

    zones = gpd.GeoDataFrame(
        {"zone_id": ["west", "east"]},
        geometry=[
            box(500_000.0, 4_499_900.0, 500_050.0, 4_500_000.0),
            box(500_050.0, 4_499_900.0, 500_100.0, 4_500_000.0),
        ],
        crs="EPSG:32618",
    )
    zones.to_file(zones_path, driver="GeoJSON")
    return dem_path, zones_path
