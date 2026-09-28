"""Unit tests for coastal and terrain features and the feature stack."""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geoflood.features.coastal import (
    connected_depth,
    connected_inundation,
    distance_to_mask,
)
from geoflood.features.stack import (
    FeatureConfig,
    build_feature_stack,
    generate_features,
    scenario_feature_name,
)
from geoflood.features.terrain import (
    local_relief,
    slope_degrees,
    topographic_wetness_index,
)
from geoflood.raster import RasterData


def _coast_with_inland_pit() -> np.ndarray:
    """Low coastal strip on the west edge; an isolated pit behind a ridge."""
    dem = np.full((9, 9), 3.0)
    dem[:, 0] = 0.0  # open water / shoreline
    dem[:, 1] = 0.5
    dem[4, 6] = 0.2  # inland depression enclosed by 3 m terrain
    return dem


def test_connected_inundation_excludes_isolated_pit() -> None:
    dem = _coast_with_inland_pit()
    valid = np.ones_like(dem, dtype=bool)

    flooded = connected_inundation(dem, valid, 1.0)

    assert flooded[:, :2].all()
    assert not flooded[4, 6], "inland pit is not connected to the coast"
    bathtub = dem < 1.0
    assert bathtub[4, 6], "the v1 bathtub would flood it"


def test_connected_inundation_uses_explicit_sources() -> None:
    dem = _coast_with_inland_pit()
    valid = np.ones_like(dem, dtype=bool)
    sources = np.zeros_like(valid)
    sources[4, 6] = True

    flooded = connected_inundation(dem, valid, 1.0, sources=sources)

    assert flooded[4, 6]
    assert not flooded[:, 0].any()


def test_connected_depth_preserves_nodata() -> None:
    dem = _coast_with_inland_pit()
    valid = np.ones_like(dem, dtype=bool)
    valid[0, 0] = False

    depth = connected_depth(dem, valid, 1.0)

    assert np.isnan(depth[0, 0])
    assert depth[1, 0] == pytest.approx(1.0)
    assert depth[4, 6] == 0.0


def test_distance_to_mask_uses_cell_size() -> None:
    mask = np.zeros((3, 5), dtype=bool)
    mask[:, 0] = True
    valid = np.ones_like(mask)

    distance = distance_to_mask(mask, valid, cell_size=(10.0, 10.0))

    np.testing.assert_allclose(distance[1], [0, 10, 20, 30, 40])


def test_distance_to_empty_mask_is_nan() -> None:
    mask = np.zeros((2, 2), dtype=bool)
    assert np.isnan(distance_to_mask(mask, ~mask, cell_size=(1, 1))).all()


def test_slope_of_uniform_plane() -> None:
    dem = np.tile(np.arange(6, dtype=np.float64) * 0.1, (4, 1))
    valid = np.ones_like(dem, dtype=bool)

    slope = slope_degrees(dem, valid, cell_size=(1.0, 1.0))

    np.testing.assert_allclose(slope, np.degrees(np.arctan(0.1)))


def test_local_relief_and_window_validation() -> None:
    dem = np.arange(25, dtype=np.float64).reshape(5, 5)
    valid = np.ones_like(dem, dtype=bool)

    relief = local_relief(dem, valid, window=3)

    assert relief[2, 2] == pytest.approx(12.0)  # 18 - 6
    with pytest.raises(ValueError, match="odd"):
        local_relief(dem, valid, window=4)


def test_twi_is_finite_on_flats() -> None:
    accumulation = np.array([[1.0, 4.0]])
    slope = np.array([[0.0, 5.0]])
    valid = np.ones_like(slope, dtype=bool)

    twi = topographic_wetness_index(accumulation, slope, valid, cell_size=(10, 10))

    assert np.isfinite(twi).all()
    assert twi[0, 0] == pytest.approx(np.log(10.0 / 1e-3))


def test_scenario_feature_names_are_stable() -> None:
    assert scenario_feature_name(1.0) == "connected_depth_1m"
    assert scenario_feature_name(0.5) == "connected_depth_0p5m"
    assert scenario_feature_name(-1.0) == "connected_depth_neg1m"


def test_build_feature_stack_rejects_geographic_crs() -> None:
    raster = RasterData(
        values=np.ones((3, 3), dtype=np.float32),
        profile={"crs": "EPSG:4326", "transform": from_origin(0, 0, 0.1, 0.1)},
        nodata=None,
    )
    with pytest.raises(ValueError, match="projected"):
        build_feature_stack(raster, FeatureConfig())


def test_generate_features_writes_aligned_products(
    tmp_path: Path, sample_data: tuple[Path, Path]
) -> None:
    dem_path, _ = sample_data
    config = FeatureConfig(
        scenario_levels=(3.2,), water_threshold=0.5, stream_threshold_cells=5
    )

    outputs = generate_features(dem_path, tmp_path / "features", config)

    with rasterio.open(dem_path) as source, rasterio.open(outputs["raster"]) as out:
        assert out.crs == source.crs
        assert out.transform == source.transform
        assert out.descriptions[0] == "elevation"
        assert "connected_depth_3p2m" in out.descriptions
        assert out.read(1)[0, 0] == out.nodata  # source nodata cell stays nodata

    table = gpd.read_parquet(outputs["table"])
    assert len(table) == 99  # 10 x 10 minus one nodata cell
    assert table.crs is not None and table.crs.to_epsg() == 32618

    metadata = json.loads(outputs["metadata"].read_text(encoding="utf-8"))
    assert metadata["vertical_datum"] is None
    assert any("Vertical datum unknown" in w for w in metadata["warnings"])
    assert metadata["features"]["is_water"]["max"] == 1.0


def test_generate_features_records_declared_vertical_datum(
    tmp_path: Path, sample_data: tuple[Path, Path]
) -> None:
    dem_path, _ = sample_data
    config = FeatureConfig(vertical_datum="NAVD88", water_threshold=0.5)

    outputs = generate_features(dem_path, tmp_path / "f", config)

    metadata = json.loads(outputs["metadata"].read_text(encoding="utf-8"))
    assert metadata["vertical_datum"] == "NAVD88"
    assert not any("Vertical datum" in w for w in metadata["warnings"])
