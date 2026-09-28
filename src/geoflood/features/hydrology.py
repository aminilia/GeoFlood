"""Grid hydrology: depression filling, D8 routing, accumulation, and HAND.

The algorithms are deliberately dependency-light (NumPy + ``heapq``) so the
feature pipeline stays installable on Python 3.11+ with NumPy 2 and is easy to
audit:

* Depression filling uses the priority-flood algorithm with an epsilon
  gradient (Barnes, Lehman & Mulla, 2014), so every filled cell drains to an
  outlet along strictly decreasing elevations.
* Flow direction is single-direction D8 (steepest descent).
* Height Above Nearest Drainage (HAND) follows Renno et al. (2008) and
  Nobre et al. (2011): each cell's elevation minus the elevation of the first
  drainage cell reached along its D8 flow path.

The Python priority queue processes roughly 10^5-10^6 cells per few seconds,
which suits study-area rasters such as the 900 x 900 Norfolk subset. Larger
tiles should be processed in blocks or with a compiled backend.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

BoolArray = npt.NDArray[np.bool_]
FloatArray64 = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

# Row/column offsets of the eight D8 neighbours.
_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


@dataclass(frozen=True)
class FlowRouting:
    """Hydrologically conditioned surface and D8 routing for one DEM.

    Attributes:
        filled: Depression-filled elevations (NaN outside ``valid``).
        receivers: Flat index of each cell's D8 receiver, ``-1`` for outlets
            and invalid cells.
        accumulation: Upstream cell count including the cell itself (0 for
            invalid cells).
        valid: Mask of cells that carry terrain data.
    """

    filled: FloatArray64
    receivers: IntArray
    accumulation: FloatArray64
    valid: BoolArray


def _seed_mask(valid: BoolArray, outlets: BoolArray | None) -> BoolArray:
    """Valid cells on the raster edge, next to nodata, or flagged as outlets."""
    padded = np.pad(valid, 1, constant_values=False)
    touches_invalid = np.zeros_like(valid)
    rows, cols = valid.shape
    for dr, dc in _OFFSETS:
        neighbour = padded[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        touches_invalid |= ~neighbour
    seeds = valid & touches_invalid
    if outlets is not None:
        seeds |= outlets & valid
    return seeds


def priority_flood_fill(
    dem: FloatArray64,
    valid: BoolArray,
    *,
    outlets: BoolArray | None = None,
    epsilon: float = 1e-4,
) -> FloatArray64:
    """Fill depressions so every valid cell drains to an outlet.

    Args:
        dem: Elevation grid (any float dtype; converted to float64).
        valid: Cells that carry terrain data.
        outlets: Optional extra drainage outlets, e.g. an open-water mask on a
            coastal DEM. Raster edges and cells next to nodata are always
            outlets.
        epsilon: Minimum rise imposed across filled flats so that D8 routing
            is well defined. Keep it far below the DEM's vertical accuracy.

    Returns:
        Filled elevations with NaN outside ``valid``.
    """
    if dem.shape != valid.shape or dem.ndim != 2:
        raise ValueError("dem and valid must be matching two-dimensional arrays")
    if epsilon < 0:
        raise ValueError("epsilon must be non-negative")

    rows, cols = dem.shape
    filled = np.where(valid, dem.astype(np.float64), np.nan)
    flat = filled.ravel()
    closed = ~valid.ravel()

    heap: list[tuple[float, int, int]] = []
    counter = 0
    for seed in np.flatnonzero(_seed_mask(valid, outlets)).tolist():
        heapq.heappush(heap, (float(flat[seed]), counter, seed))
        closed[seed] = True
        counter += 1

    while heap:
        elevation, _, index = heapq.heappop(heap)
        row, col = divmod(index, cols)
        for dr, dc in _OFFSETS:
            nr, nc = row + dr, col + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            neighbour = nr * cols + nc
            if closed[neighbour]:
                continue
            closed[neighbour] = True
            if flat[neighbour] <= elevation:
                flat[neighbour] = elevation + epsilon
            heapq.heappush(heap, (float(flat[neighbour]), counter, neighbour))
            counter += 1

    return filled


def d8_receivers(
    filled: FloatArray64,
    valid: BoolArray,
    *,
    cell_size: tuple[float, float] = (1.0, 1.0),
) -> IntArray:
    """Return the flat index of each cell's steepest-descent D8 neighbour.

    Args:
        filled: Depression-filled elevations.
        valid: Cells that carry terrain data.
        cell_size: ``(dx, dy)`` cell dimensions used to weight diagonal drops.

    Returns:
        Receiver indices, ``-1`` where no lower valid neighbour exists.
    """
    rows, cols = filled.shape
    dx, dy = abs(cell_size[0]), abs(cell_size[1])
    padded = np.pad(np.where(valid, filled, np.inf), 1, constant_values=np.inf)
    best_slope = np.zeros(filled.shape, dtype=np.float64)
    receivers = np.full(filled.shape, -1, dtype=np.int64)
    row_idx, col_idx = np.indices(filled.shape)

    for dr, dc in _OFFSETS:
        neighbour = padded[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        distance = float(np.hypot(dr * dy, dc * dx))
        with np.errstate(invalid="ignore"):
            slope = (filled - neighbour) / distance
        better = valid & np.isfinite(slope) & (slope > best_slope)
        best_slope = np.where(better, slope, best_slope)
        target = (row_idx + dr) * cols + (col_idx + dc)
        receivers = np.where(better, target, receivers)

    return receivers.ravel()


def flow_accumulation(
    filled: FloatArray64, receivers: IntArray, valid: BoolArray
) -> FloatArray64:
    """Count upstream cells (including each cell) along D8 receivers."""
    flat_valid = valid.ravel()
    accumulation = flat_valid.astype(np.float64)
    order = np.argsort(np.where(flat_valid, filled.ravel(), -np.inf))[::-1]
    for index in order:
        if not flat_valid[index]:
            break
        receiver = receivers[index]
        if receiver >= 0:
            accumulation[receiver] += accumulation[index]
    return accumulation.reshape(filled.shape)


def route_flow(
    dem: FloatArray64,
    valid: BoolArray,
    *,
    cell_size: tuple[float, float],
    outlets: BoolArray | None = None,
    epsilon: float = 1e-4,
) -> FlowRouting:
    """Fill, route, and accumulate flow for one DEM."""
    filled = priority_flood_fill(dem, valid, outlets=outlets, epsilon=epsilon)
    receivers = d8_receivers(filled, valid, cell_size=cell_size)
    accumulation = flow_accumulation(filled, receivers, valid)
    return FlowRouting(
        filled=filled, receivers=receivers, accumulation=accumulation, valid=valid
    )


def height_above_nearest_drainage(
    dem: FloatArray64,
    routing: FlowRouting,
    drainage: BoolArray,
) -> FloatArray64:
    """Compute HAND: elevation above the first drainage cell downstream.

    The value uses the unfilled ``dem`` for both the cell and its drainage cell,
    so cells inside a filled depression can be negative (below the level of
    the drainage they spill to). Cells whose flow path never reaches drainage
    are NaN.

    Args:
        dem: Original elevations.
        routing: Result of :func:`route_flow` for the same DEM.
        drainage: Channel or open-water cells that define "drainage".
    """
    flat_dem = dem.ravel().astype(np.float64)
    flat_drainage = (drainage & routing.valid).ravel()
    flat_valid = routing.valid.ravel()
    drain_elevation = np.full(flat_dem.shape, np.nan)

    # Ascending filled elevation guarantees receivers are visited first.
    order = np.argsort(np.where(flat_valid, routing.filled.ravel(), np.inf))
    for index in order:
        if not flat_valid[index]:
            break
        if flat_drainage[index]:
            drain_elevation[index] = flat_dem[index]
        else:
            receiver = routing.receivers[index]
            if receiver >= 0:
                drain_elevation[index] = drain_elevation[receiver]

    hand = flat_dem - drain_elevation
    hand[~flat_valid] = np.nan
    return np.asarray(hand.reshape(dem.shape), dtype=np.float64)
