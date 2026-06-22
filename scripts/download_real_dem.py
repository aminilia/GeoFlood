"""Download a small real USGS 3DEP DEM for the Norfolk portfolio demo."""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import rasterio

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "norfolk_elizabeth_river_dem.tif"
DEFAULT_METADATA = ROOT / "data" / "norfolk_elizabeth_river_dem.json"

SERVICE_URL = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/"
    "3DEPElevation/ImageServer/exportImage"
)
STUDY_AREA = {
    "name": "Elizabeth River and Norfolk, Virginia",
    "bbox_wgs84": [-76.31, 36.80, -76.23, 36.88],
    "output_crs": "EPSG:32618",
    "width": 900,
    "height": 900,
}


def build_download_url() -> str:
    """Build the reproducible USGS ArcGIS ImageServer export request."""
    params = {
        "bbox": ",".join(str(value) for value in STUDY_AREA["bbox_wgs84"]),
        "bboxSR": "4326",
        "imageSR": "32618",
        "size": f"{STUDY_AREA['width']},{STUDY_AREA['height']}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "noData": "-9999",
        "f": "image",
    }
    return f"{SERVICE_URL}?{urllib.parse.urlencode(params)}"


def download_real_dem(
    output_path: Path = DEFAULT_OUTPUT,
    metadata_path: Path = DEFAULT_METADATA,
) -> tuple[Path, Path]:
    """Download and validate the real DEM, then write provenance metadata."""
    url = build_download_url()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "geoflood-cicd-platform/0.1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        output_path.write_bytes(response.read())

    with rasterio.open(output_path) as dataset:
        if dataset.count != 1 or dataset.crs is None:
            raise ValueError("Downloaded file is not a valid georeferenced DEM")
        values = dataset.read(1, masked=True)
        metadata = {
            "study_area": STUDY_AREA,
            "source": "USGS National Map 3D Elevation Program (3DEP)",
            "source_service": SERVICE_URL.rsplit("/exportImage", 1)[0],
            "download_url": url,
            "accessed": date.today().isoformat(),
            "license": "Public domain; free of charge and without use restrictions",
            "vertical_units": "meters",
            "vertical_datum": None,
            "raster": {
                "path": str(output_path.relative_to(ROOT)),
                "crs": str(dataset.crs),
                "width": dataset.width,
                "height": dataset.height,
                "nodata": dataset.nodata,
                "minimum_elevation": float(values.min()),
                "maximum_elevation": float(values.max()),
            },
        }

    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path, metadata_path


def parse_args() -> argparse.Namespace:
    """Parse command-line overrides for output locations."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    dem, metadata = download_real_dem(args.output, args.metadata)
    print(f"Created {dem}")
    print(f"Created {metadata}")
