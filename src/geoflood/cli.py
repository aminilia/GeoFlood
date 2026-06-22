"""Command-line interface for GeoFlood workflows."""

from pathlib import Path
from typing import Annotated

import typer

from geoflood import __version__
from geoflood.flood_depth import run_flood_scenario
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
    """Run synthetic, static water-level flood scenarios."""


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
) -> None:
    """Create a flood-depth raster and optional polygon summary."""
    if (zones is None) != (summary is None):
        raise typer.BadParameter("--zones and --summary must be supplied together")

    try:
        result = run_flood_scenario(dem, water_level, output)
        if zones is not None and summary is not None:
            write_zonal_stats(result.output_path, zones, summary)
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


if __name__ == "__main__":
    app()
