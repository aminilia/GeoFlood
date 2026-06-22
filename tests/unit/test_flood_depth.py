"""Unit tests for the scientific flood-depth calculation."""

import numpy as np
import pytest

from geoflood.flood_depth import calculate_flood_depth


def test_calculate_flood_depth_clips_negative_values() -> None:
    terrain = np.array([[1.0, 3.2], [4.0, 2.0]], dtype=np.float32)

    result = calculate_flood_depth(terrain, 3.2)

    np.testing.assert_allclose(result, [[2.2, 0.0], [0.0, 1.2]], rtol=1e-6)


def test_calculate_flood_depth_preserves_numeric_nodata() -> None:
    terrain = np.array([[1.0, -9999.0]], dtype=np.float32)

    result = calculate_flood_depth(terrain, 3.0, nodata=-9999.0)

    assert result[0, 0] == pytest.approx(2.0)
    assert result[0, 1] == -9999.0


def test_calculate_flood_depth_preserves_nan() -> None:
    terrain = np.array([[np.nan, 4.0]], dtype=np.float32)

    result = calculate_flood_depth(terrain, 3.0)

    assert np.isnan(result[0, 0])
    assert result[0, 1] == 0.0


@pytest.mark.parametrize("water_level", [np.nan, np.inf, -np.inf])
def test_calculate_flood_depth_rejects_non_finite_water_level(
    water_level: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        calculate_flood_depth(np.ones((2, 2), dtype=np.float32), water_level)


def test_calculate_flood_depth_requires_two_dimensions() -> None:
    with pytest.raises(ValueError, match="two-dimensional"):
        calculate_flood_depth(np.ones(3, dtype=np.float32), 2.0)
