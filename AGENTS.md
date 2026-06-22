# AGENTS.md

## Mission

Maintain GeoFlood as a production-style scientific Python portfolio project. Favor reproducibility, readable geospatial logic, and operational credibility over feature count.

## Engineering rules

- Support Python 3.11 or newer and keep the package installable from
  `pyproject.toml`.
- Put reusable code in `src/geoflood`; keep scripts thin.
- Preserve raster CRS, transform, dimensions, and nodata metadata.
- Never convert nodata pixels into valid flood depths.
- Keep fixtures synthetic and small. Do not add external datasets or large
  binary files.
- Use type hints and docstrings for public functions.
- Keep CLI and API behavior backed by the same processing functions.
- Add or update tests whenever behavior changes.
- Avoid hidden network calls and machine-specific paths.

## Required checks

Run before handing off changes:

```bash
ruff check src tests scripts
black --check src tests scripts
mypy src
pytest --cov=geoflood --cov-report=term-missing
mkdocs build --strict
```

If dependencies are unavailable, report the exact failed command. Do not claim
checks passed unless they were run.

## CI/CD expectations

Keep `.gitlab-ci.yml` stages ordered as validate, test, build, scan, package,
and docs. Generated outputs should be artifacts with expiration policies.
Container jobs should use immutable or versioned images where practical.

## Scope discipline

This model is a static water-surface-minus-terrain demonstration, not a
hydrodynamic forecast. Documentation and API descriptions must not imply it
models flow velocity, rainfall-runoff, uncertainty, or real-time hazards.
