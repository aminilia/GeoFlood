"""Integration tests for HTTP validation and raster processing."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geoflood.api import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_run_flood_scenario_endpoint(
    tmp_path: Path,
    sample_data: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dem_path, _ = sample_data
    monkeypatch.setenv("GEOFLOOD_OUTPUT_DIR", str(tmp_path))

    response = client.post(
        "/run-flood-scenario",
        json={
            "dem_path": str(dem_path),
            "water_level": 3.2,
            "output_name": "api_depth.tif",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["flooded_cell_count"] > 0
    assert Path(payload["output_path"]).exists()


def test_run_flood_scenario_returns_not_found(tmp_path: Path) -> None:
    response = client.post(
        "/run-flood-scenario",
        json={
            "dem_path": str(tmp_path / "missing.tif"),
            "water_level": 3.2,
            "output_name": "missing_depth.tif",
        },
    )

    assert response.status_code == 404


def test_run_flood_scenario_validates_output_name(
    sample_data: tuple[Path, Path],
) -> None:
    dem_path, _ = sample_data

    response = client.post(
        "/run-flood-scenario",
        json={
            "dem_path": str(dem_path),
            "water_level": 3.2,
            "output_name": "../escape.tif",
        },
    )

    assert response.status_code == 422
