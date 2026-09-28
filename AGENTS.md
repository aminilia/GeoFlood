# AGENTS.md

## Mission

Maintain GeoFlood as a production-style scientific Python project. v1 is a
static bathtub flood-depth engine; v2 ("AI Flood Intelligence") extends it with
a reproducible data pipeline, terrain/hydrology features, a validated
flood-risk model, a cited document retriever, and a tool-using agent. Favor
reproducibility, readable geospatial logic, and operational credibility over
feature count.

## Engineering rules

- Support Python 3.11 or newer and keep the package installable from
  `pyproject.toml`.
- Put reusable code in `src/geoflood`; keep scripts thin.
- Preserve raster CRS, transform, dimensions, and nodata metadata.
- Never convert nodata pixels into valid flood depths.
- Keep test fixtures synthetic and small. Real datasets enter only through the
  DVC pipeline (`dvc.yaml`) with provenance; never commit large binaries to git.
- Record horizontal CRS and vertical datum for every derived product. If the
  vertical datum is unknown, say so in the output metadata; never infer it.
- Feature functions in `src/geoflood/features/` are pure array-in/array-out
  functions with unit tests on synthetic terrain whose answer is known.
- Preserve `data/norfolk_elizabeth_river_dem.json` provenance whenever the
  small real USGS study-area DEM is regenerated.
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
dvc repro --dry   # when pipeline stages change
```

If dependencies are unavailable, report the exact failed command. Do not claim
checks passed unless they were run.

## CI/CD expectations

Keep CI stages ordered as validate, test, build, scan, package, and docs in
both `.github/workflows/ci.yml` and `.gitlab-ci.yml` until one is retired. Generated outputs should be artifacts with expiration policies.
Container jobs should use immutable or versioned images where practical.

## Scope discipline

- GeoFlood is not a hydrodynamic model or an operational forecast. Nothing in
  code, docs, or API descriptions may imply real-time warning, flow velocity,
  or rainfall-runoff simulation.
- Bathtub and connected-bathtub outputs are static screening products; label
  them as such.
- Model outputs (v2 Phase 2 onward) may be described as probabilities only
  when calibration has been measured on spatially held-out data, and the
  metric is reported next to the claim.
- Any number an LLM-based component returns must come from a tool result or a
  cited document passage. The LLM does not compute numbers itself.
