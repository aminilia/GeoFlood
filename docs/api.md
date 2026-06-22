# API

Run locally with:

```bash
uvicorn geoflood.api:app --reload
```

FastAPI publishes interactive OpenAPI documentation at `/docs` and the schema
at `/openapi.json`.

## `GET /health`

Returns service status and package version.

```json
{"status": "healthy", "version": "0.1.0"}
```

## `POST /run-flood-scenario`

Request:

```json
{
  "dem_path": "tests/data/sample_dem.tif",
  "water_level": 3.2,
  "output_name": "api_depth.tif"
}
```

Response:

```json
{
  "output_path": "C:/project/outputs/api_depth.tif",
  "water_level": 3.2,
  "valid_cell_count": 99,
  "flooded_cell_count": 52,
  "max_depth": 3.139394,
  "mean_depth": 0.842118,
  "warnings": []
}
```

The path must be visible inside the API process. With Docker Compose, reference
the sample input as `/data/sample_dem.tif`. Generated files are placed in
`GEOFLOOD_OUTPUT_DIR`, which defaults to `outputs`.

### Status codes

| Code | Meaning |
| --- | --- |
| `200` | Scenario completed |
| `404` | DEM path was not found |
| `422` | Request validation or raster processing failed |
