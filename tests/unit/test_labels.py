"""Unit tests for FEMA NFHL flood-zone labels."""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from geoflood.labels.fema import (
    LABEL_NODATA,
    ZoneClass,
    build_zone_labels,
    classify_zone,
    rasterize_zones,
    sfha_from_classes,
    write_zone_labels,
)


@pytest.mark.parametrize(
    ("zone", "subtype", "expected"),
    [
        ("VE", None, ZoneClass.V_ZONE),
        ("AE", None, ZoneClass.A_ZONE),
        ("AH", "", ZoneClass.A_ZONE),
        ("AO", None, ZoneClass.A_ZONE),
        ("A12", None, ZoneClass.A_ZONE),
        ("X", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD", ZoneClass.X_SHADED),
        ("X", "AREA WITH REDUCED FLOOD RISK DUE TO LEVEE", ZoneClass.X_SHADED),
        ("X", "AREA OF MINIMAL FLOOD HAZARD", ZoneClass.X_MINIMAL),
        ("D", None, ZoneClass.UNDETERMINED_D),
        ("OPEN WATER", None, ZoneClass.OPEN_WATER),
        ("AREA NOT INCLUDED", None, ZoneClass.UNMAPPED),
        (None, None, ZoneClass.UNMAPPED),
    ],
)
def test_classify_zone(zone: str | None, subtype: str | None, expected: int) -> None:
    assert classify_zone(zone, subtype) == expected


def test_sfha_from_classes_marks_excluded_cells_nodata() -> None:
    classes = np.array(
        [
            [ZoneClass.V_ZONE, ZoneClass.A_ZONE, ZoneClass.X_SHADED],
            [ZoneClass.X_MINIMAL, ZoneClass.OPEN_WATER, ZoneClass.UNMAPPED],
        ],
        dtype=np.uint8,
    )

    sfha = sfha_from_classes(classes)

    np.testing.assert_array_equal(sfha, [[1, 1, 0], [0, LABEL_NODATA, LABEL_NODATA]])


def _profile() -> dict[str, object]:
    return {
        "crs": "EPSG:32618",
        "transform": from_origin(500_000.0, 4_500_000.0, 10.0, 10.0),
        "height": 4,
        "width": 4,
    }


def test_rasterize_zones_most_hazardous_class_wins_overlap() -> None:
    zones = gpd.GeoDataFrame(
        {
            "FLD_ZONE": ["X", "AE", "VE"],
            "ZONE_SUBTY": ["AREA OF MINIMAL FLOOD HAZARD", None, None],
        },
        geometry=[
            box(500_000, 4_499_960, 500_040, 4_500_000),  # whole grid
            box(500_000, 4_499_960, 500_020, 4_500_000),  # west half
            box(500_000, 4_499_980, 500_010, 4_500_000),  # NW column, top 2 rows
        ],
        crs="EPSG:32618",
    )

    classes = rasterize_zones(zones, _profile())

    assert classes[0, 0] == ZoneClass.V_ZONE
    assert classes[3, 0] == ZoneClass.A_ZONE
    assert classes[0, 3] == ZoneClass.X_MINIMAL


def test_rasterize_zones_reprojects_geographic_polygons() -> None:
    utm = gpd.GeoSeries([box(500_000, 4_499_960, 500_040, 4_500_000)], crs=32618)
    zones = gpd.GeoDataFrame(
        {"FLD_ZONE": ["AE"], "ZONE_SUBTY": [None]},
        geometry=utm.to_crs(4326),
        crs="EPSG:4326",
    )

    classes = rasterize_zones(zones, _profile())

    assert (classes[1:-1, 1:-1] == ZoneClass.A_ZONE).all()


def test_rasterize_zones_requires_crs() -> None:
    zones = gpd.GeoDataFrame({"FLD_ZONE": ["AE"]}, geometry=[box(0, 0, 1, 1)])
    with pytest.raises(ValueError, match="CRS"):
        rasterize_zones(zones, _profile())


def test_build_and_write_zone_labels(
    tmp_path: Path, sample_data: tuple[Path, Path]
) -> None:
    dem_path, _ = sample_data
    zones_path = tmp_path / "nfhl.geojson"
    gpd.GeoDataFrame(
        {"FLD_ZONE": ["AE", "X"], "ZONE_SUBTY": [None, "0.2 PCT ANNUAL CHANCE"]},
        geometry=[
            box(500_000, 4_499_900, 500_050, 4_500_000),
            box(500_050, 4_499_900, 500_100, 4_500_000),
        ],
        crs="EPSG:32618",
    ).to_file(zones_path, driver="GeoJSON")
    zones_path.with_suffix(".json").write_text(
        json.dumps({"dfirm_ids": ["TEST"]}), encoding="utf-8"
    )

    labels = build_zone_labels(dem_path, zones_path)
    outputs = write_zone_labels(
        labels, tmp_path / "labels", source_dem=dem_path, source_zones=zones_path
    )

    with rasterio.open(outputs["raster"]) as dataset:
        assert dataset.descriptions == ("fema_zone_class", "sfha")
        sfha = dataset.read(2)
    np.testing.assert_array_equal(sfha[:, :5], 1)
    np.testing.assert_array_equal(sfha[:, 5:], 0)
    metadata = json.loads(outputs["metadata"].read_text(encoding="utf-8"))
    assert metadata["sfha_positive_rate"] == pytest.approx(0.5)
    assert metadata["source_provenance"] == {"dfirm_ids": ["TEST"]}
    assert "STATIC_BFE" in metadata["leakage_guard"]
