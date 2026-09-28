"""Coastal inundation features: connected bathtub and distance to water."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy import ndimage

BoolArray = npt.NDArray[np.bool_]
FloatArray64 = npt.NDArray[np.float64]

_EIGHT_CONNECTED = np.ones((3, 3), dtype=bool)


def boundary_mask(shape: tuple[int, int]) -> BoolArray:
    """Return a mask of the outermost ring of cells."""
    mask = np.zeros(shape, dtype=bool)
    mask[0, :] = mask[-1, :] = mask[:, 0] = mask[:, -1] = True
    return mask


def connected_inundation(
    dem: FloatArray64,
    valid: BoolArray,
    water_level: float,
    *,
    sources: BoolArray | None = None,
) -> BoolArray:
    """Return cells below ``water_level`` that connect to a water source.

    Unlike the v1 bathtub, a low cell floods only if an 8-connected path of
    below-water-level cells links it to a source. This removes isolated inland
    depressions that a static coastal surge could not reach.

    Args:
        dem: Elevations in the same vertical datum as ``water_level``.
        valid: Cells that carry terrain data.
        water_level: Static water-surface elevation.
        sources: Cells where water enters (e.g. an open-water mask). Defaults to
            below-water-level cells on the raster boundary, i.e. an open
            boundary on every side.
    """
    if not np.isfinite(water_level):
        raise ValueError("Water level must be finite")
    below = valid & (np.where(valid, dem, np.inf) < water_level)
    seed = boundary_mask(dem.shape) if sources is None else sources
    labels, count = ndimage.label(below, structure=_EIGHT_CONNECTED)
    if count == 0:
        return np.zeros(dem.shape, dtype=bool)
    connected_labels = np.unique(labels[below & seed])
    connected_labels = connected_labels[connected_labels > 0]
    return np.isin(labels, connected_labels)


def connected_depth(
    dem: FloatArray64,
    valid: BoolArray,
    water_level: float,
    *,
    sources: BoolArray | None = None,
) -> FloatArray64:
    """Depth ``water_level - dem`` on connected cells, 0 elsewhere, NaN if invalid."""
    flooded = connected_inundation(dem, valid, water_level, sources=sources)
    depth = np.where(flooded, water_level - dem, 0.0)
    depth[~valid] = np.nan
    return depth


def distance_to_mask(
    mask: BoolArray,
    valid: BoolArray,
    *,
    cell_size: tuple[float, float],
) -> FloatArray64:
    """Euclidean distance (map units) from each cell to the nearest mask cell.

    Returns NaN everywhere when the mask is empty, and NaN outside ``valid``.
    """
    if not mask.any():
        return np.full(mask.shape, np.nan)
    dx, dy = abs(cell_size[0]), abs(cell_size[1])
    distance = ndimage.distance_transform_edt(~mask, sampling=(dy, dx))
    result = np.asarray(distance, dtype=np.float64)
    result[~valid] = np.nan
    return result
