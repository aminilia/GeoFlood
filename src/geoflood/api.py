"""FastAPI service exposing GeoFlood processing operations."""

from fastapi import FastAPI, HTTPException

from geoflood import __version__
from geoflood.config import (
    FloodScenarioRequest,
    FloodScenarioResponse,
    Settings,
)
from geoflood.flood_depth import run_flood_scenario

app = FastAPI(
    title="GeoFlood API",
    version=__version__,
    description=(
        "Generate static flood-depth rasters from a DEM and constant "
        "water-surface elevation."
    ),
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Report process health for local orchestration and container probes."""
    return {"status": "healthy", "version": __version__}


@app.post(
    "/run-flood-scenario",
    response_model=FloodScenarioResponse,
    tags=["processing"],
)
def run_scenario(request: FloodScenarioRequest) -> FloodScenarioResponse:
    """Run a path-based scenario using files mounted into the API container."""
    settings = Settings()
    output_path = settings.output_dir / request.output_name
    try:
        result = run_flood_scenario(
            request.dem_path,
            request.water_level,
            output_path,
            max_cells=settings.max_raster_cells,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return FloodScenarioResponse(**result.__dict__)
