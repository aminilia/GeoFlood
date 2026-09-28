"""Unit tests for depression filling, D8 routing, accumulation, and HAND."""

import numpy as np
import pytest

from geoflood.features.hydrology import (
    d8_receivers,
    height_above_nearest_drainage,
    priority_flood_fill,
    route_flow,
)


def _east_ramp(rows: int = 5, cols: int = 6) -> np.ndarray:
    """Plane that falls toward the east edge by 1 unit per cell."""
    return np.tile(np.arange(cols, 0, -1, dtype=np.float64), (rows, 1))


def _v_valley(rows: int = 7, cols: int = 9) -> np.ndarray:
    """Valley whose floor is the centre column at elevation 0."""
    centre = cols // 2
    return np.tile(np.abs(np.arange(cols) - centre).astype(np.float64), (rows, 1))


def test_priority_flood_fills_pit_to_spill_level() -> None:
    dem = np.full((5, 5), 5.0)
    dem[2, 2] = 1.0  # pit surrounded by 5 m terrain
    valid = np.ones_like(dem, dtype=bool)

    filled = priority_flood_fill(dem, valid, epsilon=0.0)

    assert filled[2, 2] == pytest.approx(5.0)
    np.testing.assert_array_equal(filled[dem == 5.0], 5.0)


def test_priority_flood_preserves_nodata_and_leaves_ramp_unchanged() -> None:
    dem = _east_ramp()
    valid = np.ones_like(dem, dtype=bool)
    valid[0, 0] = False

    filled = priority_flood_fill(dem, valid)

    assert np.isnan(filled[0, 0])
    np.testing.assert_allclose(filled[valid], dem[valid])


def test_every_filled_cell_drains_to_lower_receiver() -> None:
    rng = np.random.default_rng(42)
    dem = rng.uniform(0, 10, size=(20, 20))
    valid = np.ones_like(dem, dtype=bool)

    routing = route_flow(dem, valid, cell_size=(1.0, 1.0))

    flat = routing.filled.ravel()
    interior = np.zeros_like(valid)
    interior[1:-1, 1:-1] = True
    receivers = routing.receivers[interior.ravel()]
    assert (receivers >= 0).all(), "interior cells must have a receiver"
    assert (flat[receivers] < flat[interior.ravel()]).all()


def test_d8_on_ramp_points_east() -> None:
    dem = _east_ramp()
    valid = np.ones_like(dem, dtype=bool)

    receivers = d8_receivers(dem, valid, cell_size=(1.0, 1.0)).reshape(dem.shape)

    index = np.arange(dem.size).reshape(dem.shape)
    np.testing.assert_array_equal(receivers[:, :-1], index[:, 1:])
    np.testing.assert_array_equal(receivers[:, -1], -1)


def test_accumulation_counts_upstream_cells() -> None:
    dem = _east_ramp(rows=4, cols=6)
    valid = np.ones_like(dem, dtype=bool)

    routing = route_flow(dem, valid, cell_size=(1.0, 1.0))

    expected = np.tile(np.arange(1, 7, dtype=np.float64), (4, 1))
    np.testing.assert_array_equal(routing.accumulation, expected)


def test_hand_in_v_valley_equals_distance_above_floor() -> None:
    dem = _v_valley()
    valid = np.ones_like(dem, dtype=bool)
    drainage = dem == 0.0

    routing = route_flow(dem, valid, cell_size=(1.0, 1.0))
    hand = height_above_nearest_drainage(dem, routing, drainage)

    np.testing.assert_allclose(hand, dem)


def test_hand_is_nan_when_path_never_reaches_drainage() -> None:
    dem = _east_ramp()
    valid = np.ones_like(dem, dtype=bool)
    drainage = np.zeros_like(valid)

    routing = route_flow(dem, valid, cell_size=(1.0, 1.0))
    hand = height_above_nearest_drainage(dem, routing, drainage)

    assert np.isnan(hand).all()


def test_priority_flood_rejects_mismatched_shapes() -> None:
    with pytest.raises(ValueError, match="matching"):
        priority_flood_fill(np.zeros((3, 3)), np.ones((2, 2), dtype=bool))
