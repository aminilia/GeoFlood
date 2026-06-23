"""GeoFlood package metadata.

The package initializer intentionally avoids importing geospatial runtime
modules so lightweight operations such as version discovery do not load
Rasterio or its native GDAL dependencies.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
