"""Assemble per-cell features from a DEM and write them as versionable products.

Outputs, all written side by side into one directory:

* ``features.tif`` - multiband Cloud-Optimized GeoTIFF, one band per feature,
  band descriptions set to feature names.
* ``features.parquet`` - GeoParquet table, one row per valid cell with its
  centre point, row/column, and every feature.
* ``features.json`` - metadata: CRS, vertical datum, configuration, feature
  descriptions, per-feature summary statistics, and source provenance.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import rasterio
from rasterio.crs import CRS

from geoflood import __version__
from geoflood.features.coastal import connected_depth, distance_to_mask
from geoflood.features.hydrology import height_above_nearest_drainage, route_flow
from geoflood.features.terrain import (
    local_relief,
    slope_degrees,
    topographic_wetness_index,
)
from geoflood.raster import RasterData, read_raster

FloatArray64 = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class FeatureConfig:
    """Parameters that control feature generation.

    Attributes:
        reference_level: Elevation of a reference water level (for example MHHW)
            in the DEM's vertical datum. ``elev_above_reference`` is measured
            from it.
        scenario_levels: Water levels (DEM datum) for connected-bathtub depth
            features, one feature per level.
        water_threshold: Cells at or below this elevation are treated as open
            water: drainage outlets for routing, drainage for HAND, and sources
            for connected inundation. ``None`` disables the water mask.
        stream_threshold_cells: Upstream cell count at which a cell counts as a
            drainage channel for HAND.
        relief_window: Odd window size for local relief.
        fill_epsilon: Rise imposed across filled flats (DEM units).
        vertical_datum: Vertical datum of the DEM when known (e.g. ``NAVD88``).
            Recorded in metadata only; never inferred.
    """

    reference_level: float = 0.0
    scenario_levels: tuple[float, ...] = (1.0, 2.0)
    water_threshold: float | None = None
    stream_threshold_cells: int = 200
    relief_window: int = 5
    fill_epsilon: float = 1e-4
    vertical_datum: str | None = None


FEATURE_DESCRIPTIONS: dict[str, str] = {
    "elevation": "DEM elevation (DEM vertical datum and units)",
    "elev_above_reference": "Elevation minus the configured reference level",
    "slope_deg": "Slope in degrees (central differences)",
    "local_relief": "Max minus min elevation in the relief window",
    "log_flow_accumulation": "ln(1 + upstream D8 cell count)",
    "twi": "Topographic wetness index ln(a / tan(beta))",
    "hand": "Height above nearest drainage (may be negative in depressions)",
    "distance_to_water": "Distance to nearest open-water cell (map units)",
    "is_water": "1 where the cell is in the open-water mask",
}


@dataclass
class FeatureStack:
    """Named feature grids plus the raster profile they share."""

    features: dict[str, FloatArray64]
    valid: BoolArray
    profile: dict[str, Any]
    config: FeatureConfig
    descriptions: dict[str, str] = field(default_factory=dict)

    @property
    def names(self) -> list[str]:
        """Feature names in band order."""
        return list(self.features)


def _cell_size(profile: dict[str, Any]) -> tuple[float, float]:
    transform = profile["transform"]
    return float(abs(transform.a)), float(abs(transform.e))


def _require_projected(profile: dict[str, Any]) -> None:
    crs = profile.get("crs")
    if crs is None:
        raise ValueError("Feature generation requires a DEM with a CRS")
    if CRS.from_user_input(crs).is_geographic:
        raise ValueError(
            "Feature generation requires a projected CRS in metres; "
            "reproject the DEM first"
        )


def scenario_feature_name(level: float) -> str:
    """Stable feature name for a connected-depth scenario level."""
    return f"connected_depth_{level:g}m".replace("-", "neg").replace(".", "p")


def build_feature_stack(raster: RasterData, config: FeatureConfig) -> FeatureStack:
    """Compute every configured feature for one DEM."""
    _require_projected(raster.profile)
    dem = raster.values.astype(np.float64)
    valid = np.isfinite(dem)
    if raster.nodata is not None and not math.isnan(raster.nodata):
        valid &= dem != raster.nodata
    if not valid.any():
        raise ValueError("DEM has no valid cells")
    dem = np.where(valid, dem, np.nan)
    cell_size = _cell_size(raster.profile)

    water = (
        valid & (np.where(valid, dem, np.inf) <= config.water_threshold)
        if config.water_threshold is not None
        else np.zeros_like(valid)
    )
    routing = route_flow(
        dem,
        valid,
        cell_size=cell_size,
        outlets=water if water.any() else None,
        epsilon=config.fill_epsilon,
    )
    drainage = water | (routing.accumulation >= config.stream_threshold_cells)
    slope = slope_degrees(dem, valid, cell_size=cell_size)

    features: dict[str, FloatArray64] = {
        "elevation": dem,
        "elev_above_reference": dem - config.reference_level,
        "slope_deg": slope,
        "local_relief": local_relief(dem, valid, window=config.relief_window),
        "log_flow_accumulation": np.where(
            valid, np.log1p(routing.accumulation), np.nan
        ),
        "twi": topographic_wetness_index(
            routing.accumulation, slope, valid, cell_size=cell_size
        ),
        "hand": height_above_nearest_drainage(dem, routing, drainage),
        "distance_to_water": distance_to_mask(water, valid, cell_size=cell_size),
        "is_water": np.where(valid, water.astype(np.float64), np.nan),
    }
    descriptions = dict(FEATURE_DESCRIPTIONS)
    sources = water if water.any() else None
    for level in config.scenario_levels:
        name = scenario_feature_name(level)
        depth = connected_depth(dem, valid, level, sources=sources)
        depth[water] = 0.0  # open water is the source, not flooded land
        features[name] = depth
        descriptions[name] = (
            f"Connected-bathtub depth on land for a static {level:g} m water "
            "level; 0 on open water and where not connected to a source"
        )

    return FeatureStack(
        features=features,
        valid=valid,
        profile=raster.profile,
        config=config,
        descriptions=descriptions,
    )


def _summary(values: FloatArray64) -> dict[str, float | int | None]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"count": 0, "min": None, "mean": None, "max": None}
    return {
        "count": int(finite.size),
        "min": round(float(finite.min()), 4),
        "mean": round(float(finite.mean()), 4),
        "max": round(float(finite.max()), 4),
    }


def write_feature_raster(stack: FeatureStack, path: Path) -> Path:
    """Write all features as one multiband Cloud-Optimized GeoTIFF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    nodata = -9999.0
    data = np.stack(
        [np.where(np.isfinite(a), a, nodata) for a in stack.features.values()]
    ).astype(np.float32)
    profile = {
        "driver": "COG",
        "dtype": "float32",
        "count": data.shape[0],
        "height": data.shape[1],
        "width": data.shape[2],
        "crs": stack.profile["crs"],
        "transform": stack.profile["transform"],
        "nodata": nodata,
        "compress": "deflate",
        "predictor": 3,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(data)
        for band, name in enumerate(stack.names, start=1):
            dataset.set_band_description(band, name)
    return path


def write_feature_table(stack: FeatureStack, path: Path) -> Path:
    """Write one GeoParquet row per valid cell with its centre point."""
    import geopandas as gpd
    import pandas as pd

    rows, cols = np.nonzero(stack.valid)
    transform = stack.profile["transform"]
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    frame = pd.DataFrame({"row": rows.astype(np.int32), "col": cols.astype(np.int32)})
    for name, values in stack.features.items():
        frame[name] = values[rows, cols].astype(np.float32)
    table = gpd.GeoDataFrame(
        frame,
        geometry=gpd.points_from_xy(xs, ys),
        crs=stack.profile["crs"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=False)
    return path


def write_feature_metadata(
    stack: FeatureStack,
    path: Path,
    *,
    source_dem: Path,
    provenance: dict[str, Any] | None,
) -> Path:
    """Write feature metadata and summary statistics as JSON."""
    crs = stack.profile["crs"]
    vertical_datum = stack.config.vertical_datum
    if vertical_datum is None and provenance is not None:
        vertical_datum = provenance.get("vertical_datum")
    metadata = {
        "generator": f"geoflood {__version__}",
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_dem": source_dem.as_posix(),
        "crs": CRS.from_user_input(crs).to_string(),
        "vertical_datum": vertical_datum,
        "cell_size": list(_cell_size(stack.profile)),
        "shape": [int(stack.valid.shape[0]), int(stack.valid.shape[1])],
        "valid_cells": int(stack.valid.sum()),
        "config": asdict(stack.config),
        "features": {
            name: {
                "description": stack.descriptions.get(name, ""),
                **_summary(values),
            }
            for name, values in stack.features.items()
        },
        "warnings": _warnings(stack, vertical_datum),
        "source_provenance": provenance,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return path


def _warnings(stack: FeatureStack, vertical_datum: str | None) -> list[str]:
    warnings: list[str] = []
    if vertical_datum is None:
        warnings.append(
            "Vertical datum unknown: elevation-based features and scenario "
            "levels cannot be compared with tidal datums until it is set."
        )
    if stack.config.water_threshold is None:
        warnings.append(
            "No open-water mask: HAND uses channels only and connected "
            "inundation assumes an open boundary on every raster edge."
        )
    hand = stack.features["hand"]
    unreached = int((stack.valid & ~np.isfinite(hand)).sum())
    if unreached:
        warnings.append(f"{unreached} cells never reach drainage; HAND is NaN there.")
    return warnings


def load_provenance(
    dem_path: Path, provenance_path: Path | None
) -> dict[str, Any] | None:
    """Load explicit provenance JSON, or a same-stem JSON beside the DEM."""
    candidate = provenance_path or dem_path.with_suffix(".json")
    if candidate.is_file():
        loaded: dict[str, Any] = json.loads(candidate.read_text(encoding="utf-8"))
        return loaded
    return None


def generate_features(
    dem_path: Path,
    output_dir: Path,
    config: FeatureConfig,
    *,
    provenance_path: Path | None = None,
    max_cells: int | None = None,
) -> dict[str, Path]:
    """Read a DEM, compute features, and write raster, table, and metadata."""
    raster = read_raster(dem_path, max_cells=max_cells)
    stack = build_feature_stack(raster, config)
    provenance = load_provenance(dem_path, provenance_path)
    return {
        "raster": write_feature_raster(stack, output_dir / "features.tif"),
        "table": write_feature_table(stack, output_dir / "features.parquet"),
        "metadata": write_feature_metadata(
            stack,
            output_dir / "features.json",
            source_dem=dem_path,
            provenance=provenance,
        ),
    }
