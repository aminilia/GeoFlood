"""Generate a compact JSON quality report for a flood-depth raster."""

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio


def generate_report(raster_path: Path, output_path: Path) -> Path:
    """Write machine-readable raster metadata and flood-depth statistics."""
    with rasterio.open(raster_path) as dataset:
        values = dataset.read(1, masked=True)
        valid = values.compressed()
        flooded = valid[valid > 0]
        report = {
            "raster": str(raster_path),
            "crs": str(dataset.crs),
            "width": dataset.width,
            "height": dataset.height,
            "valid_cell_count": int(valid.size),
            "flooded_cell_count": int(flooded.size),
            "flooded_fraction": (
                float(flooded.size / valid.size) if valid.size else 0.0
            ),
            "mean_depth": float(np.mean(valid)) if valid.size else 0.0,
            "max_depth": float(np.max(valid)) if valid.size else 0.0,
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--raster", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"Created {generate_report(args.raster, args.output)}")
