"""Integration tests for the installed CLI workflow."""

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from typer.testing import CliRunner

from geoflood.cli import app

runner = CliRunner()


def test_cli_run_creates_raster_and_zonal_summary(
    tmp_path: Path, sample_data: tuple[Path, Path]
) -> None:
    dem_path, zones_path = sample_data
    output = tmp_path / "flood_depth.tif"
    summary = tmp_path / "zonal_stats.csv"

    result = runner.invoke(
        app,
        [
            "run",
            "--dem",
            str(dem_path),
            "--water-level",
            "3.2",
            "--output",
            str(output),
            "--zones",
            str(zones_path),
            "--summary",
            str(summary),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Flooded cells:" in result.output
    assert output.exists()
    assert summary.exists()
    assert len(pd.read_csv(summary)) == 2
    with rasterio.open(output) as dataset:
        assert dataset.crs is not None
        assert dataset.nodata == -9999.0


def test_cli_requires_zones_and_summary_together(
    tmp_path: Path, sample_data: tuple[Path, Path]
) -> None:
    dem_path, zones_path = sample_data

    result = runner.invoke(
        app,
        [
            "run",
            "--dem",
            str(dem_path),
            "--water-level",
            "3.2",
            "--output",
            str(tmp_path / "depth.tif"),
            "--zones",
            str(zones_path),
        ],
    )

    assert result.exit_code != 0
    assert "--zones and --summary" in result.output


def test_cli_prints_suspicious_depth_warning(tmp_path: Path) -> None:
    dem = tmp_path / "negative_dem.tif"
    with rasterio.open(
        dem,
        "w",
        driver="GTiff",
        width=2,
        height=1,
        count=1,
        dtype="float32",
        crs="EPSG:32618",
        transform=rasterio.transform.from_origin(500_000, 4_500_000, 10, 10),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(np.array([[-3.0, 1.0]], dtype=np.float32), 1)

    report = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "run",
            "--dem",
            str(dem),
            "--water-level",
            "2.0",
            "--output",
            str(tmp_path / "depth.tif"),
            "--report",
            str(report),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "GEOFLOOD DATA QUALITY WARNINGS" in result.output
    assert "WARNING:" in result.output
    assert "exceeds the scenario water level" in result.output
    assert report.exists()
