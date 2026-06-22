"""Scenario-level quality reporting for DEM and flood-depth raster pairs."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds

from geoflood.flood_depth import build_scenario_warnings


@dataclass(frozen=True)
class ScenarioReport:
    """Scientific statistics, spatial metadata, and visible validation warnings."""

    location_name: str | None
    dem_source: str | None
    dem_source_url: str | None
    dem_download_date: str | None
    vertical_datum: str | None
    scenario_water_level_m: float
    crs: str | None
    horizontal_crs: str | None
    bbox_projected: tuple[float, float, float, float]
    bbox_lonlat: tuple[float, float, float, float] | None
    width: int
    height: int
    cell_size_x_m: float
    cell_size_y_m: float
    valid_cell_count: int
    flooded_cell_count: int
    flooded_fraction: float
    total_area_m2: float
    total_area_km2: float
    flooded_area_m2: float
    flooded_area_km2: float
    flooded_area_acres: float
    estimated_flood_volume_m3: float
    mean_depth_all_cells_m: float
    mean_depth_flooded_cells_m: float
    max_depth_m: float
    min_dem_elevation_m: float | None
    max_dem_elevation_m: float | None
    min_flooded_dem_elevation_m: float | None
    max_flooded_dem_elevation_m: float | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


def _validate_alignment(
    dem: rasterio.io.DatasetReader, depth: rasterio.io.DatasetReader
) -> None:
    """Require identical grids so cell-by-cell statistics remain meaningful."""
    if dem.shape != depth.shape:
        raise ValueError("DEM and flood-depth raster dimensions do not match")
    if dem.transform != depth.transform:
        raise ValueError("DEM and flood-depth raster transforms do not match")
    if dem.crs != depth.crs:
        raise ValueError("DEM and flood-depth raster CRS values do not match")


def _load_provenance(dem_path: Path, provenance_path: Path | None) -> dict[str, object]:
    """Load an explicit or same-stem JSON provenance record when available."""
    candidate = provenance_path or dem_path.with_suffix(".json")
    if not candidate.is_file():
        return {}
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("DEM provenance JSON must contain an object")
    return payload


def _provenance_fields(
    provenance: dict[str, object],
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Extract stable report fields from the repository provenance schema."""
    study_area = provenance.get("study_area")
    location_name = (
        study_area.get("name")
        if isinstance(study_area, dict) and isinstance(study_area.get("name"), str)
        else None
    )
    source = provenance.get("source")
    source_url = provenance.get("download_url") or provenance.get("source_service")
    download_date = provenance.get("accessed")
    vertical_datum = provenance.get("vertical_datum")
    return (
        location_name,
        source if isinstance(source, str) else None,
        source_url if isinstance(source_url, str) else None,
        download_date if isinstance(download_date, str) else None,
        vertical_datum if isinstance(vertical_datum, str) else None,
    )


def create_scenario_report(
    dem_path: Path,
    flood_depth_path: Path,
    scenario_water_level_m: float,
    provenance_path: Path | None = None,
) -> ScenarioReport:
    """Calculate a quality report from an aligned DEM and depth raster."""
    provenance = _load_provenance(dem_path, provenance_path)
    (
        location_name,
        dem_source,
        dem_source_url,
        dem_download_date,
        vertical_datum,
    ) = _provenance_fields(provenance)
    with (
        rasterio.open(dem_path) as dem,
        rasterio.open(flood_depth_path) as depth,
    ):
        _validate_alignment(dem, depth)
        dem_values = dem.read(1).astype(np.float32, copy=False)
        depth_values = depth.read(1).astype(np.float32, copy=False)

        dem_valid = np.isfinite(dem_values)
        if dem.nodata is not None and not np.isnan(dem.nodata):
            dem_valid &= dem_values != dem.nodata
        depth_valid = np.isfinite(depth_values)
        if depth.nodata is not None and not np.isnan(depth.nodata):
            depth_valid &= depth_values != depth.nodata
        valid_mask = dem_valid & depth_valid
        flooded_mask = valid_mask & (depth_values > 0)

        valid_dem = dem_values[valid_mask]
        valid_depth = depth_values[valid_mask]
        flooded_dem = dem_values[flooded_mask]
        flooded_depth = depth_values[flooded_mask]
        valid_count = int(valid_depth.size)
        flooded_count = int(flooded_depth.size)

        cell_size_x = abs(float(dem.transform.a))
        cell_size_y = abs(float(dem.transform.e))
        cell_area = abs(
            float(dem.transform.a * dem.transform.e - dem.transform.b * dem.transform.d)
        )
        total_area_m2 = valid_count * cell_area
        flooded_area_m2 = flooded_count * cell_area
        mean_flooded_depth = float(flooded_depth.mean()) if flooded_count else 0.0
        bounds = (
            float(dem.bounds.left),
            float(dem.bounds.bottom),
            float(dem.bounds.right),
            float(dem.bounds.top),
        )
        transformed_bounds = (
            transform_bounds(
                dem.crs,
                "EPSG:4326",
                *dem.bounds,
                densify_pts=21,
            )
            if dem.crs is not None
            else None
        )
        lonlat_bounds = (
            (
                float(transformed_bounds[0]),
                float(transformed_bounds[1]),
                float(transformed_bounds[2]),
                float(transformed_bounds[3]),
            )
            if transformed_bounds is not None
            else None
        )
        warnings = list(
            build_scenario_warnings(
                dem_values,
                depth_values,
                scenario_water_level_m,
                nodata=dem.nodata,
                has_crs=dem.crs is not None,
            )
        )
        if dem.crs is not None and not dem.crs.is_projected:
            warnings.append(
                "CRS is not projected; cell_size_*_m and flooded_area_m2 are "
                "reported from coordinate units and are not reliable metric values."
            )

        return ScenarioReport(
            location_name=location_name,
            dem_source=dem_source,
            dem_source_url=dem_source_url,
            dem_download_date=dem_download_date,
            vertical_datum=vertical_datum,
            scenario_water_level_m=scenario_water_level_m,
            crs=str(dem.crs) if dem.crs is not None else None,
            horizontal_crs=str(dem.crs) if dem.crs is not None else None,
            bbox_projected=bounds,
            bbox_lonlat=lonlat_bounds,
            width=dem.width,
            height=dem.height,
            cell_size_x_m=cell_size_x,
            cell_size_y_m=cell_size_y,
            valid_cell_count=valid_count,
            flooded_cell_count=flooded_count,
            flooded_fraction=(flooded_count / valid_count if valid_count else 0.0),
            total_area_m2=total_area_m2,
            total_area_km2=total_area_m2 / 1_000_000.0,
            flooded_area_m2=flooded_area_m2,
            flooded_area_km2=flooded_area_m2 / 1_000_000.0,
            flooded_area_acres=flooded_area_m2 / 4_046.8564224,
            estimated_flood_volume_m3=mean_flooded_depth * flooded_area_m2,
            mean_depth_all_cells_m=(float(valid_depth.mean()) if valid_count else 0.0),
            mean_depth_flooded_cells_m=mean_flooded_depth,
            max_depth_m=float(valid_depth.max(initial=0.0)),
            min_dem_elevation_m=(float(valid_dem.min()) if valid_dem.size else None),
            max_dem_elevation_m=(float(valid_dem.max()) if valid_dem.size else None),
            min_flooded_dem_elevation_m=(
                float(flooded_dem.min()) if flooded_dem.size else None
            ),
            max_flooded_dem_elevation_m=(
                float(flooded_dem.max()) if flooded_dem.size else None
            ),
            warnings=tuple(warnings),
        )


def write_scenario_report(
    dem_path: Path,
    flood_depth_path: Path,
    scenario_water_level_m: float,
    output_path: Path,
    provenance_path: Path | None = None,
) -> Path:
    """Write an indented JSON scenario report."""
    report = create_scenario_report(
        dem_path,
        flood_depth_path,
        scenario_water_level_m,
        provenance_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
