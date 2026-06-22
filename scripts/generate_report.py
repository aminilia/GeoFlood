"""Generate a validated JSON report for a DEM and flood-depth scenario."""

import argparse
from pathlib import Path

from geoflood.reporting import write_scenario_report


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dem", type=Path, required=True)
    parser.add_argument("--raster", type=Path, required=True)
    parser.add_argument("--water-level", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    report = write_scenario_report(
        args.dem,
        args.raster,
        args.water_level,
        args.output,
        args.provenance,
    )
    print(f"Created {report}")
