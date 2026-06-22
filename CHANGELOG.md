# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and
this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### [0.1.0] - 2026-06-18

- Nodata-safe flood-depth raster processing engine.
- Typer CLI and FastAPI service.
- Synthetic DEM and polygon fixture generation.
- Unit and integration test suites with coverage enforcement.
- Docker, GitLab CI/CD, MkDocs, security scanning, and package build workflows.

## [0.1.1] - 2026-06-22

- Initial portfolio release.
- Added a reproducible USGS 3DEP DEM and provenance workflow for the Elizabeth
  River and Norfolk, Virginia study area.
- Added scenario-level DEM diagnostics, metric area/depth statistics, and
  visible warnings for negative elevations, metadata gaps, and depth values
  exceeding the configured water level.
- Added DEM source provenance, projected and geographic bounds, area unit
  conversions, and estimated bathtub-scenario flood volume to JSON reports.
