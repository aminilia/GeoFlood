"""Raster input, validation, and output utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import rasterio

FloatArray = npt.NDArray[np.float32]


@dataclass(frozen=True)
class RasterData:
    """In-memory single-band raster and the metadata needed to reproduce it."""

    values: FloatArray
    profile: dict[str, Any]
    nodata: float | None


def read_raster(path: Path, *, max_cells: int | None = None) -> RasterData:
    """Read a single-band raster as floating-point data.

    Args:
        path: GeoTIFF to read.
        max_cells: Optional guard against unexpectedly large rasters.

    Raises:
        FileNotFoundError: If the input does not exist.
        ValueError: If the raster is multiband, empty, or exceeds the cell limit.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Raster not found: {path}")

    with rasterio.open(path) as dataset:
        if dataset.count != 1:
            raise ValueError("GeoFlood currently requires a single-band DEM")
        cell_count = dataset.width * dataset.height
        if cell_count == 0:
            raise ValueError("Raster has no cells")
        if max_cells is not None and cell_count > max_cells:
            raise ValueError(
                f"Raster has {cell_count:,} cells; configured limit is {max_cells:,}"
            )
        values = dataset.read(1).astype(np.float32, copy=False)
        return RasterData(
            values=values, profile=dataset.profile.copy(), nodata=dataset.nodata
        )


def write_raster(
    path: Path,
    values: FloatArray,
    source_profile: dict[str, Any],
    *,
    nodata: float | None,
) -> Path:
    """Write a compressed, single-band GeoTIFF while preserving spatial metadata."""
    if values.ndim != 2:
        raise ValueError("Output raster values must be a two-dimensional array")

    path.parent.mkdir(parents=True, exist_ok=True)
    profile = source_profile.copy()
    profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        height=values.shape[0],
        width=values.shape[1],
        nodata=nodata,
        compress="deflate",
        predictor=3,
    )
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(values.astype(np.float32, copy=False), 1)
    return path
