"""Unit tests for raster I/O behavior."""

from pathlib import Path

import numpy as np
import pytest
import rasterio

from geoflood.flood_depth import run_flood_scenario
from geoflood.raster import read_raster, write_raster


def test_read_raster_returns_values_and_metadata(
    sample_data: tuple[Path, Path],
) -> None:
    dem_path, _ = sample_data

    raster = read_raster(dem_path)

    assert raster.values.shape == (10, 10)
    assert raster.nodata == -9999.0
    assert str(raster.profile["crs"]) == "EPSG:32618"


def test_read_raster_enforces_cell_limit(sample_data: tuple[Path, Path]) -> None:
    dem_path, _ = sample_data

    with pytest.raises(ValueError, match="configured limit"):
        read_raster(dem_path, max_cells=99)


def test_write_raster_preserves_spatial_metadata(
    tmp_path: Path, sample_data: tuple[Path, Path]
) -> None:
    dem_path, _ = sample_data
    source = read_raster(dem_path)
    output = tmp_path / "copy.tif"

    write_raster(output, source.values, source.profile, nodata=source.nodata)

    with rasterio.open(dem_path) as original, rasterio.open(output) as copied:
        assert copied.crs == original.crs
        assert copied.transform == original.transform
        assert copied.shape == original.shape


def test_run_flood_scenario_writes_expected_output(
    tmp_path: Path, sample_data: tuple[Path, Path]
) -> None:
    dem_path, _ = sample_data
    output = tmp_path / "depth.tif"

    result = run_flood_scenario(dem_path, 3.2, output)

    assert output.exists()
    assert 0 < result.flooded_cell_count < result.valid_cell_count
    assert result.max_depth == pytest.approx(3.1393938)
    with rasterio.open(output) as dataset:
        values = dataset.read(1)
        assert values[0, 0] == dataset.nodata
        assert np.all(values[values != dataset.nodata] >= 0)
