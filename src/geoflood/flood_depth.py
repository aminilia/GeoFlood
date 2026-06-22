"""Flood-depth model and end-to-end raster processing service."""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt

from geoflood.raster import FloatArray, read_raster, write_raster


@dataclass(frozen=True)
class FloodResult:
    """Summary statistics and location of a generated flood-depth raster."""

    output_path: Path
    water_level: float
    valid_cell_count: int
    flooded_cell_count: int
    max_depth: float
    mean_depth: float


def _nodata_mask(terrain: FloatArray, nodata: float | None) -> npt.NDArray[np.bool_]:
    """Build a mask that handles both explicit and NaN nodata conventions."""
    mask = np.isnan(terrain)
    if nodata is not None and not np.isnan(nodata):
        mask |= terrain == nodata
    return mask


def calculate_flood_depth(
    terrain: FloatArray,
    water_level: float,
    *,
    nodata: float | None = None,
) -> FloatArray:
    """Calculate ``max(water_level - terrain, 0)`` and preserve nodata cells."""
    if terrain.ndim != 2:
        raise ValueError("Terrain must be a two-dimensional array")
    if not np.isfinite(water_level):
        raise ValueError("Water level must be finite")

    nodata_mask = _nodata_mask(terrain, nodata)
    depth = cast(
        FloatArray,
        np.maximum(np.float32(water_level) - terrain, 0).astype(np.float32),
    )
    if nodata is None:
        depth[nodata_mask] = np.nan
    else:
        depth[nodata_mask] = np.float32(nodata)
    return depth


def run_flood_scenario(
    dem_path: Path,
    water_level: float,
    output_path: Path,
    *,
    max_cells: int | None = None,
) -> FloodResult:
    """Run the flood model for a DEM and persist a spatially aligned GeoTIFF."""
    source = read_raster(dem_path, max_cells=max_cells)
    depth = calculate_flood_depth(source.values, water_level, nodata=source.nodata)
    write_raster(output_path, depth, source.profile, nodata=source.nodata)

    valid_mask = ~_nodata_mask(depth, source.nodata)
    valid_depth = depth[valid_mask]
    flooded_cell_count = int(np.count_nonzero(valid_depth > 0))
    return FloodResult(
        output_path=output_path.resolve(),
        water_level=water_level,
        valid_cell_count=int(valid_depth.size),
        flooded_cell_count=flooded_cell_count,
        max_depth=float(valid_depth.max(initial=0.0)),
        mean_depth=float(valid_depth.mean()) if valid_depth.size else 0.0,
    )
