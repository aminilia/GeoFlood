"""Local terrain descriptors: slope, relief, and topographic wetness index."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy import ndimage

BoolArray = npt.NDArray[np.bool_]
FloatArray64 = npt.NDArray[np.float64]


def slope_degrees(
    dem: FloatArray64,
    valid: BoolArray,
    *,
    cell_size: tuple[float, float],
) -> FloatArray64:
    """Slope in degrees from central differences.

    Invalid neighbours are replaced by the cell's own value first, so slopes at
    nodata edges are one-sided rather than contaminated by fill values.
    """
    dx, dy = abs(cell_size[0]), abs(cell_size[1])
    surface = np.where(valid, dem, np.nan)
    # Fill gaps with the nearest valid value so gradients stay finite.
    if (~valid).any() and valid.any():
        nearest = ndimage.distance_transform_edt(
            ~valid, return_distances=False, return_indices=True
        )
        surface = surface[tuple(nearest)]
    grad_y, grad_x = np.gradient(surface, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(grad_x, grad_y)))
    slope[~valid] = np.nan
    return np.asarray(slope, dtype=np.float64)


def local_relief(
    dem: FloatArray64, valid: BoolArray, *, window: int = 5
) -> FloatArray64:
    """Maximum minus minimum elevation in a square moving window."""
    if window < 3 or window % 2 == 0:
        raise ValueError("window must be an odd integer of at least 3")
    high = ndimage.maximum_filter(np.where(valid, dem, -np.inf), size=window)
    low = ndimage.minimum_filter(np.where(valid, dem, np.inf), size=window)
    relief = np.asarray(high - low, dtype=np.float64)
    relief[~valid] = np.nan
    return relief


def topographic_wetness_index(
    accumulation: FloatArray64,
    slope_deg: FloatArray64,
    valid: BoolArray,
    *,
    cell_size: tuple[float, float],
    min_tan_slope: float = 1e-3,
) -> FloatArray64:
    """TWI = ln(a / tan(beta)), with ``a`` the specific catchment area.

    ``a`` is upstream cell count x cell area / contour width (one cell width).
    ``tan(beta)`` is floored at ``min_tan_slope`` so flat cells stay finite.
    """
    dx, dy = abs(cell_size[0]), abs(cell_size[1])
    specific_area = accumulation * (dx * dy) / dx
    tan_slope = np.maximum(np.tan(np.radians(slope_deg)), min_tan_slope)
    with np.errstate(divide="ignore", invalid="ignore"):
        twi = np.log(specific_area / tan_slope)
    twi = np.asarray(twi, dtype=np.float64)
    twi[~valid] = np.nan
    return twi
