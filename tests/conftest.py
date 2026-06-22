"""Shared test fixtures."""

from pathlib import Path

import pytest
from scripts.generate_sample_data import generate_sample_data


@pytest.fixture(scope="session")
def sample_data(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Create deterministic raster and vector inputs once per test session."""
    return generate_sample_data(tmp_path_factory.mktemp("sample_data"))
