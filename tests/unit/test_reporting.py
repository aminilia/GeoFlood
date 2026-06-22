"""Tests for scenario diagnostics and JSON report statistics."""

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geoflood.flood_depth import run_flood_scenario
from geoflood.reporting import create_scenario_report, write_scenario_report


def _write_dem(
    path: Path,
    values: np.ndarray,
    *,
    crs: str | None = "EPSG:32618",
    nodata: float | None = -9999.0,
) -> Path:
    """Write a compact DEM fixture with 10-meter cells."""
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype="float32",
        crs=crs,
        transform=from_origin(500_000.0, 4_500_000.0, 10.0, 10.0),
        nodata=nodata,
    ) as dataset:
        dataset.write(values.astype(np.float32), 1)
    return path


def test_negative_dem_warns_when_depth_exceeds_water_level(tmp_path: Path) -> None:
    dem = _write_dem(
        tmp_path / "negative_dem.tif",
        np.array([[-2.0, 0.0], [1.0, 3.0]], dtype=np.float32),
    )

    result = run_flood_scenario(dem, 2.0, tmp_path / "depth.tif")

    assert result.max_depth == pytest.approx(4.0)
    assert any("below -1.0 m" in warning for warning in result.warnings)
    assert any(
        "exceeds the scenario water level" in warning for warning in result.warnings
    )


def test_report_has_all_cell_and_flooded_cell_means(tmp_path: Path) -> None:
    dem = _write_dem(
        tmp_path / "dem.tif",
        np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32),
    )
    depth = tmp_path / "depth.tif"
    run_flood_scenario(dem, 2.0, depth)

    report = create_scenario_report(dem, depth, 2.0)

    assert report.mean_depth_all_cells_m == pytest.approx(0.75)
    assert report.mean_depth_flooded_cells_m == pytest.approx(1.5)
    assert report.flooded_cell_count == 2
    assert report.flooded_area_m2 == pytest.approx(200.0)
    assert report.flooded_area_km2 == pytest.approx(0.0002)
    assert report.flooded_area_acres == pytest.approx(0.0494211)
    assert report.total_area_m2 == pytest.approx(400.0)
    assert report.total_area_km2 == pytest.approx(0.0004)
    assert report.estimated_flood_volume_m3 == pytest.approx(300.0)
    assert report.min_flooded_dem_elevation_m == pytest.approx(0.0)
    assert report.max_flooded_dem_elevation_m == pytest.approx(1.0)
    assert report.horizontal_crs == "EPSG:32618"
    assert report.bbox_projected == pytest.approx(
        (500_000.0, 4_499_980.0, 500_020.0, 4_500_000.0)
    )
    assert report.bbox_lonlat is not None


def test_json_report_keeps_visible_max_depth_warning(tmp_path: Path) -> None:
    dem = _write_dem(
        tmp_path / "negative_dem.tif",
        np.array([[-3.0, 1.0]], dtype=np.float32),
    )
    depth = tmp_path / "depth.tif"
    output = tmp_path / "report.json"
    run_flood_scenario(dem, 2.0, depth)

    write_scenario_report(dem, depth, 2.0, output)
    contents = output.read_text(encoding="utf-8")

    assert '"scenario_water_level_m": 2.0' in contents
    assert '"mean_depth_all_cells_m"' in contents
    assert '"mean_depth_flooded_cells_m"' in contents
    assert "exceeds the scenario water level" in contents


def test_report_warns_for_missing_crs_and_nodata(tmp_path: Path) -> None:
    dem = _write_dem(
        tmp_path / "unreferenced_dem.tif",
        np.array([[0.0, 1.0]], dtype=np.float32),
        crs=None,
        nodata=None,
    )
    depth = tmp_path / "depth.tif"
    run_flood_scenario(dem, 2.0, depth)

    report = create_scenario_report(dem, depth, 2.0)

    assert report.crs is None
    assert any("no CRS metadata" in warning for warning in report.warnings)
    assert any("no nodata metadata" in warning for warning in report.warnings)


def test_report_includes_dem_provenance_fields(tmp_path: Path) -> None:
    dem = _write_dem(
        tmp_path / "provenance_dem.tif",
        np.array([[0.0, 1.0]], dtype=np.float32),
    )
    provenance = tmp_path / "provenance_dem.json"
    provenance.write_text(
        json.dumps(
            {
                "study_area": {"name": "Test River Estuary"},
                "source": "Authoritative DEM Program",
                "download_url": "https://example.gov/dem.tif",
                "accessed": "2026-06-22",
                "vertical_datum": "NAVD88",
            }
        ),
        encoding="utf-8",
    )
    depth = tmp_path / "depth.tif"
    run_flood_scenario(dem, 2.0, depth)

    report = create_scenario_report(dem, depth, 2.0)
    payload = report.to_dict()

    assert payload["location_name"] == "Test River Estuary"
    assert payload["dem_source"] == "Authoritative DEM Program"
    assert payload["dem_source_url"] == "https://example.gov/dem.tif"
    assert payload["dem_download_date"] == "2026-06-22"
    assert payload["vertical_datum"] == "NAVD88"
    for field in (
        "horizontal_crs",
        "bbox_projected",
        "bbox_lonlat",
        "total_area_m2",
        "total_area_km2",
        "flooded_area_km2",
        "flooded_area_acres",
        "estimated_flood_volume_m3",
    ):
        assert field in payload
