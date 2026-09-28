"""Download FEMA NFHL flood-hazard zones for a study area (standard library only).

Queries FEMA's public National Flood Hazard Layer map service for every
flood-hazard-zone polygon intersecting a WGS 84 bounding box, plus the FIRM
panels (with effective dates) covering it, and writes:

* ``<out>.geojson`` - flood-hazard-zone polygons in EPSG:4326
* ``<out>.json``    - provenance: service URLs, query, access time, DFIRM IDs,
                      panel effective dates, zone counts

The default bounding box is read from the Norfolk DEM provenance so labels and
features cover the same area. Run it wherever the internet is reachable:

    python scripts/download_nfhl.py
    python scripts/download_nfhl.py --bbox -76.31 36.80 -76.23 36.88 \
        --out data/nfhl/norfolk_nfhl
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SERVICE = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
ZONE_LAYER = 28  # Flood Hazard Zones (S_FLD_HAZ_AR)
PANEL_LAYER = 3  # FIRM Panels (S_FIRM_PAN)
ZONE_FIELDS = (
    "DFIRM_ID,FLD_AR_ID,STUDY_TYP,FLD_ZONE,ZONE_SUBTY,SFHA_TF,"
    "STATIC_BFE,V_DATUM,DEPTH,LEN_UNIT,SOURCE_CIT"
)
PAGE_SIZE = 1000
# The NFHL server returns HTTP 500 for full-resolution geometry; generalizing
# to ~1 m (1e-5 degrees), far below the 10 m label grid, makes queries succeed.
MAX_ALLOWABLE_OFFSET_DEG = "0.00001"
GEOMETRY_PRECISION = "7"
RETRIES = 3
DEFAULT_PROVENANCE = Path("data/norfolk_elizabeth_river_dem.json")


def _get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}", headers={"User-Agent": "geoflood-nfhl-download"}
    )
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == RETRIES:
                raise
            print(f"NFHL server returned {exc.code}; retrying ({attempt}/{RETRIES})")
            time.sleep(5 * attempt)
    if "error" in payload:
        raise RuntimeError(f"NFHL service error: {payload['error']}")
    return payload


def _envelope(bbox: tuple[float, float, float, float]) -> dict[str, str]:
    return {
        "geometry": ",".join(str(v) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
    }


def fetch_zones(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    """Return all flood-hazard polygons in the bbox as one GeoJSON collection."""
    url = f"{SERVICE}/{ZONE_LAYER}/query"
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _get_json(
            url,
            {
                **_envelope(bbox),
                "outFields": ZONE_FIELDS,
                "outSR": "4326",
                "maxAllowableOffset": MAX_ALLOWABLE_OFFSET_DEG,
                "geometryPrecision": GEOMETRY_PRECISION,
                "orderByFields": "OBJECTID",
                "resultOffset": str(offset),
                "resultRecordCount": str(PAGE_SIZE),
                "f": "geojson",
            },
        )
        batch = page.get("features", [])
        features.extend(batch)
        exceeded = page.get("exceededTransferLimit") or page.get("properties", {}).get(
            "exceededTransferLimit"
        )
        if not batch or not exceeded:
            break
        offset += len(batch)
    return {"type": "FeatureCollection", "features": features}


def fetch_panels(bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    """Return FIRM panel IDs and effective dates intersecting the bbox."""
    payload = _get_json(
        f"{SERVICE}/{PANEL_LAYER}/query",
        {
            **_envelope(bbox),
            "outFields": "DFIRM_ID,FIRM_PAN,PANEL_TYP,EFF_DATE",
            "returnGeometry": "false",
            "f": "json",
        },
    )
    panels = []
    for feature in payload.get("features", []):
        attributes = feature["attributes"]
        effective = attributes.get("EFF_DATE")
        panels.append(
            {
                "dfirm_id": attributes.get("DFIRM_ID"),
                "panel": attributes.get("FIRM_PAN"),
                "panel_type": attributes.get("PANEL_TYP"),
                "effective_date": (
                    datetime.fromtimestamp(effective / 1000, UTC).date().isoformat()
                    if effective is not None
                    else None
                ),
            }
        )
    return sorted(panels, key=lambda p: str(p["panel"]))


def default_bbox() -> tuple[float, float, float, float]:
    """Read the study-area bbox from the committed DEM provenance."""
    record = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
    west, south, east, north = record["study_area"]["bbox_wgs84"]
    return float(west), float(south), float(east), float(north)


def main() -> None:
    """Download zones and panels and write GeoJSON plus provenance."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="WGS 84 bounding box; defaults to the Norfolk DEM study area.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/nfhl/norfolk_nfhl"),
        help="Output path without extension.",
    )
    args = parser.parse_args()
    bbox = tuple(args.bbox) if args.bbox else default_bbox()

    zones = fetch_zones(bbox)
    panels = fetch_panels(bbox)
    zone_counts = Counter(
        f"{f['properties'].get('FLD_ZONE')}|{f['properties'].get('ZONE_SUBTY') or ''}"
        for f in zones["features"]
    )
    provenance = {
        "source": "FEMA National Flood Hazard Layer (NFHL)",
        "service": SERVICE,
        "zone_layer": ZONE_LAYER,
        "panel_layer": PANEL_LAYER,
        "bbox_wgs84": list(bbox),
        "accessed_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "feature_count": len(zones["features"]),
        "dfirm_ids": sorted(
            {str(f["properties"].get("DFIRM_ID")) for f in zones["features"]}
        ),
        "zone_counts": dict(sorted(zone_counts.items())),
        "firm_panels": panels,
        "geometry_generalization_deg": float(MAX_ALLOWABLE_OFFSET_DEG),
        "license": "Public domain (U.S. federal government data)",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    geojson_path = args.out.with_suffix(".geojson")
    geojson_path.write_text(json.dumps(zones), encoding="utf-8")
    args.out.with_suffix(".json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(zones['features'])} polygons to {geojson_path}")
    print(f"Panels: {len(panels)}; DFIRMs: {', '.join(provenance['dfirm_ids'])}")


if __name__ == "__main__":
    main()
