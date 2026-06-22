"""Application configuration and API data contracts."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="GEOFLOOD_")

    output_dir: Path = Path("outputs")
    max_raster_cells: int = 25_000_000


class FloodScenarioRequest(BaseModel):
    """Validated request for a path-based flood-depth scenario."""

    dem_path: Path = Field(description="DEM GeoTIFF path visible to the API process")
    water_level: float = Field(
        ge=-500.0,
        le=10_000.0,
        description="Constant water-surface elevation in DEM vertical units",
    )
    output_name: str = Field(
        default="api_flood_depth.tif",
        min_length=5,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.tif$",
    )

    @field_validator("dem_path")
    @classmethod
    def dem_must_be_tiff(cls, value: Path) -> Path:
        """Reject unsupported input formats before processing."""
        if value.suffix.lower() not in {".tif", ".tiff"}:
            raise ValueError("dem_path must reference a .tif or .tiff file")
        return value


class FloodScenarioResponse(BaseModel):
    """Serializable summary returned by the API."""

    output_path: Path
    water_level: float
    valid_cell_count: int
    flooded_cell_count: int
    max_depth: float
    mean_depth: float
    warnings: list[str]
