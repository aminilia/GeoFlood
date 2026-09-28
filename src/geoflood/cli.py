"""Command-line interface for GeoFlood workflows."""

from pathlib import Path
from typing import Annotated

import typer

from geoflood import __version__
from geoflood.flood_depth import run_flood_scenario
from geoflood.reporting import write_scenario_report
from geoflood.zonal_stats import write_zonal_stats

app = typer.Typer(
    name="geoflood",
    help="Reproducible flood-depth raster processing.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print the package version and exit."""
    if value:
        typer.echo(f"geoflood {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Run static water-level flood scenarios."""


@app.command()
def run(
    dem: Annotated[
        Path,
        typer.Option(
            "--dem",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Input single-band DEM GeoTIFF.",
        ),
    ],
    water_level: Annotated[
        float,
        typer.Option("--water-level", help="Water-surface elevation in DEM units."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Output flood-depth GeoTIFF."),
    ],
    zones: Annotated[
        Path | None,
        typer.Option(
            "--zones",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Optional polygon dataset for zonal statistics.",
        ),
    ] = None,
    summary: Annotated[
        Path | None,
        typer.Option("--summary", help="CSV destination when --zones is supplied."),
    ] = None,
    report: Annotated[
        Path | None,
        typer.Option("--report", help="Optional JSON scenario quality report."),
    ] = None,
    provenance: Annotated[
        Path | None,
        typer.Option(
            "--provenance",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Optional DEM provenance JSON; same-stem JSON is auto-detected.",
        ),
    ] = None,
) -> None:
    """Create a flood-depth raster and optional polygon summary."""
    if (zones is None) != (summary is None):
        raise typer.BadParameter("--zones and --summary must be supplied together")

    try:
        result = run_flood_scenario(dem, water_level, output)
        if zones is not None and summary is not None:
            write_zonal_stats(result.output_path, zones, summary)
        if report is not None:
            write_scenario_report(
                dem,
                result.output_path,
                water_level,
                report,
                provenance,
            )
    except (FileNotFoundError, ValueError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Created: {result.output_path}")
    typer.echo(
        f"Flooded cells: {result.flooded_cell_count}/{result.valid_cell_count}; "
        f"maximum depth: {result.max_depth:.3f}"
    )
    if summary is not None:
        typer.echo(f"Zonal summary: {summary.resolve()}")
    if report is not None:
        typer.echo(f"Scenario report: {report.resolve()}")
    if result.warnings:
        typer.echo("", err=True)
        typer.echo("=== GEOFLOOD DATA QUALITY WARNINGS ===", err=True)
        for warning in result.warnings:
            typer.echo(f"- WARNING: {warning}", err=True)
        typer.echo("======================================", err=True)


@app.command()
def features(
    dem: Annotated[
        Path,
        typer.Option(
            "--dem",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Input single-band DEM GeoTIFF in a projected CRS.",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for features.tif/.parquet/.json."),
    ],
    water_threshold: Annotated[
        float | None,
        typer.Option(
            "--water-threshold",
            help="Cells at or below this elevation are treated as open water.",
        ),
    ] = None,
    reference_level: Annotated[
        float,
        typer.Option(
            "--reference-level",
            help="Reference water level (e.g. MHHW) in the DEM's vertical datum.",
        ),
    ] = 0.0,
    scenario_level: Annotated[
        list[float] | None,
        typer.Option(
            "--scenario-level",
            help="Static water level for a connected-depth feature; repeatable.",
        ),
    ] = None,
    stream_threshold: Annotated[
        int,
        typer.Option(
            "--stream-threshold", min=1, help="Upstream cells that define a channel."
        ),
    ] = 200,
    vertical_datum: Annotated[
        str | None,
        typer.Option(
            "--vertical-datum",
            help="Declared DEM vertical datum (e.g. NAVD88); recorded, not inferred.",
        ),
    ] = None,
    provenance: Annotated[
        Path | None,
        typer.Option(
            "--provenance",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Optional DEM provenance JSON; same-stem JSON is auto-detected.",
        ),
    ] = None,
) -> None:
    """Generate terrain, hydrology, and coastal features from a DEM."""
    from geoflood.features.stack import FeatureConfig, generate_features

    config = FeatureConfig(
        reference_level=reference_level,
        scenario_levels=tuple(scenario_level) if scenario_level else (1.0, 2.0),
        water_threshold=water_threshold,
        stream_threshold_cells=stream_threshold,
        vertical_datum=vertical_datum,
    )
    try:
        outputs = generate_features(dem, output_dir, config, provenance_path=provenance)
    except (FileNotFoundError, ValueError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for kind, path in outputs.items():
        typer.echo(f"Created {kind}: {path}")


@app.command()
def labels(
    dem: Annotated[
        Path,
        typer.Option(
            "--dem",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="DEM whose grid the labels are burned onto.",
        ),
    ],
    zones: Annotated[
        Path,
        typer.Option(
            "--zones",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="FEMA NFHL flood-hazard polygons (GeoJSON, GeoPackage, ...).",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for labels.tif and labels.json."),
    ],
) -> None:
    """Rasterize FEMA NFHL flood zones onto a DEM grid as training labels."""
    from geoflood.labels.fema import build_zone_labels, write_zone_labels

    try:
        zone_labels = build_zone_labels(dem, zones)
        outputs = write_zone_labels(
            zone_labels, output_dir, source_dem=dem, source_zones=zones
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for kind, path in outputs.items():
        typer.echo(f"Created {kind}: {path}")


if __name__ == "__main__":
    app()
