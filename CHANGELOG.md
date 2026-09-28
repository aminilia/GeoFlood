# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and
this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### 0.2.0.dev0 - GeoFlood v2, Phase 1 (data pipeline and features)

- Added `geoflood.features`: priority-flood depression filling, D8 flow
  routing and accumulation, height above nearest drainage (HAND), connected
  bathtub inundation, distance to water, slope, local relief, and topographic
  wetness index, each with unit tests on terrain with known answers.
- Added `geoflood features` CLI command writing a multiband COG, a GeoParquet
  feature table, and a JSON metadata/metrics file with vertical-datum warnings.
- Added DVC pipeline (`dvc.yaml`, `params.yaml`, `dvc.lock`) for the Norfolk
  study area and a `pipeline` optional dependency group.
- Added GitHub Actions CI mirroring the GitLab stage order.
- Rewrote AGENTS.md engineering and scope rules for v2.
- Removed duplicate `dependency_scan` and `container_scan` job definitions from
  `.gitlab-ci.yml`, a duplicate README Author section, and the committed
  `site/` build output. Aligned `__version__` with `pyproject.toml`.

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
