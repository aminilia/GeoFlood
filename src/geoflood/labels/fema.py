"""FEMA NFHL flood-zone labels on the DEM grid.

Each cell receives the class of the NFHL flood-hazard polygon covering its
centre. Where polygons overlap, the more hazardous class wins. The resulting
labels describe FEMA's *regulatory* map, not observed flooding; see
``docs/labels.md`` for what a model trained on them may claim.

Only zone fields decide the class. Attributes that encode the answer
(``STATIC_BFE``, ``DEPTH``, ``SFHA_TF``) must never be used as model features.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import rasterio
from rasterio import features as rio_features

from geoflood import __version__
from geoflood.raster import read_raster

UInt8Array = npt.NDArray[np.uint8]

LABEL_NODATA = 255


class ZoneClass(IntEnum):
    """Label classes, ordered so that a larger value is more hazardous."""

    UNMAPPED = 0
    OPEN_WATER = 1
    UNDETERMINED_D = 2
    X_MINIMAL = 3
    X_SHADED = 4
    A_ZONE = 5
    V_ZONE = 6


SFHA_CLASSES = frozenset({ZoneClass.A_ZONE, ZoneClass.V_ZONE})
NON_SFHA_CLASSES = frozenset({ZoneClass.X_MINIMAL, ZoneClass.X_SHADED})
_A_ZONES = frozenset({"A", "AE", "AH", "AO", "AR", "A99", "A1-30"})
_V_ZONES = frozenset({"V", "VE", "V1-30"})


def classify_zone(fld_zone: str | None, zone_subtype: str | None) -> ZoneClass:
    """Map NFHL ``FLD_ZONE`` and ``ZONE_SUBTY`` to a :class:`ZoneClass`."""
    zone = (fld_zone or "").strip().upper()
    subtype = (zone_subtype or "").strip().upper()
    if zone in _V_ZONES:
        return ZoneClass.V_ZONE
    if zone in _A_ZONES or (zone.startswith("A") and zone[1:].isdigit()):
        return ZoneClass.A_ZONE
    if zone == "X":
        if "0.2 PCT" in subtype or "LEVEE" in subtype or "1 PCT" in subtype:
            return ZoneClass.X_SHADED
        return ZoneClass.X_MINIMAL
    if zone == "D":
        return ZoneClass.UNDETERMINED_D
    if zone == "OPEN WATER":
        return ZoneClass.OPEN_WATER
    return ZoneClass.UNMAPPED


@dataclass(frozen=True)
class ZoneLabels:
    """Per-cell zone classes plus the derived binary SFHA label."""

    classes: UInt8Array
    sfha: UInt8Array  # 1 SFHA, 0 non-SFHA, LABEL_NODATA elsewhere
    profile: dict[str, Any]


def sfha_from_classes(classes: UInt8Array) -> UInt8Array:
    """Binary SFHA label; cells outside SFHA and X classes are nodata."""
    sfha = np.full(classes.shape, LABEL_NODATA, dtype=np.uint8)
    sfha[np.isin(classes, [int(c) for c in NON_SFHA_CLASSES])] = 0
    sfha[np.isin(classes, [int(c) for c in SFHA_CLASSES])] = 1
    return sfha


def rasterize_zones(
    zones: Any,
    profile: dict[str, Any],
) -> UInt8Array:
    """Burn NFHL polygons onto a raster grid by cell centre.

    Args:
        zones: GeoDataFrame with ``FLD_ZONE``/``ZONE_SUBTY`` columns and a CRS.
        profile: Rasterio profile of the target grid (``crs``, ``transform``,
            ``height``, ``width``).
    """
    if zones.crs is None:
        raise ValueError("Flood-zone polygons have no CRS")
    projected = zones.to_crs(profile["crs"])
    subtypes = (
        projected["ZONE_SUBTY"]
        if "ZONE_SUBTY" in projected
        else [None] * len(projected)
    )
    classes = [
        int(classify_zone(zone, subtype))
        for zone, subtype in zip(projected["FLD_ZONE"], subtypes, strict=True)
    ]
    # Burn in ascending hazard order so the most hazardous class wins overlaps.
    order = np.argsort(classes, kind="stable")
    shapes = [
        (projected.geometry.iloc[i], classes[i])
        for i in order
        if projected.geometry.iloc[i] is not None and classes[i] > 0
    ]
    shape = (int(profile["height"]), int(profile["width"]))
    if not shapes:
        return np.zeros(shape, dtype=np.uint8)
    burned = rio_features.rasterize(
        shapes,
        out_shape=shape,
        transform=profile["transform"],
        fill=int(ZoneClass.UNMAPPED),
        dtype="uint8",
        all_touched=False,
    )
    return np.asarray(burned, dtype=np.uint8)


def build_zone_labels(dem_path: Path, zones_path: Path) -> ZoneLabels:
    """Rasterize NFHL polygons onto a DEM's grid."""
    import geopandas as gpd

    raster = read_raster(dem_path)
    zones = gpd.read_file(zones_path)
    classes = rasterize_zones(zones, raster.profile)
    return ZoneLabels(
        classes=classes, sfha=sfha_from_classes(classes), profile=raster.profile
    )


def _class_shares(classes: UInt8Array) -> dict[str, dict[str, float | int]]:
    total = classes.size
    shares: dict[str, dict[str, float | int]] = {}
    for zone_class in ZoneClass:
        count = int((classes == zone_class).sum())
        shares[zone_class.name] = {
            "code": int(zone_class),
            "cells": count,
            "share": round(count / total, 4),
        }
    return shares


def write_zone_labels(
    labels: ZoneLabels,
    output_dir: Path,
    *,
    source_dem: Path,
    source_zones: Path,
) -> dict[str, Path]:
    """Write a two-band label GeoTIFF (class, sfha) and JSON metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    raster_path = output_dir / "labels.tif"
    profile = {
        "driver": "COG",
        "dtype": "uint8",
        "count": 2,
        "height": labels.classes.shape[0],
        "width": labels.classes.shape[1],
        "crs": labels.profile["crs"],
        "transform": labels.profile["transform"],
        "nodata": LABEL_NODATA,
        "compress": "deflate",
    }
    with rasterio.open(raster_path, "w", **profile) as dataset:
        dataset.write(labels.classes, 1)
        dataset.write(labels.sfha, 2)
        dataset.set_band_description(1, "fema_zone_class")
        dataset.set_band_description(2, "sfha")

    provenance_path = source_zones.with_suffix(".json")
    provenance = (
        json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance_path.is_file()
        else None
    )
    sfha_valid = labels.sfha != LABEL_NODATA
    metadata = {
        "generator": f"geoflood {__version__}",
        "label": "FEMA NFHL flood-zone class at cell centre",
        "meaning": (
            "Regulatory flood-zone designation on the effective FIRM; "
            "not observed flooding"
        ),
        "source_dem": source_dem.as_posix(),
        "source_zones": source_zones.as_posix(),
        "classes": _class_shares(labels.classes),
        "sfha_positive_rate": (
            round(float(labels.sfha[sfha_valid].mean()), 4)
            if sfha_valid.any()
            else None
        ),
        "leakage_guard": [
            "STATIC_BFE",
            "DEPTH",
            "SFHA_TF",
            "ZONE_SUBTY",
            "DFIRM_ID",
            "SOURCE_CIT",
        ],
        "source_provenance": provenance,
    }
    metadata_path = output_dir / "labels.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {"raster": raster_path, "metadata": metadata_path}
