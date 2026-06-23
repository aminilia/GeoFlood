"""Generate repository sample data using the installed GeoFlood package."""

from pathlib import Path

from geoflood.sample_data import generate_sample_data

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "tests" / "data"


if __name__ == "__main__":
    dem, zones = generate_sample_data(DATA_DIR)
    print(f"Created {dem}")
    print(f"Created {zones}")
