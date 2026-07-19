"""The ubuntu-cast command-line interface."""

from __future__ import annotations

from typing import Annotated

import typer

from . import __version__, discovery, doctor, ui

app = typer.Typer(
    name="ubuntu-cast",
    help="Cast your Ubuntu desktop — screen and audio — to a Chromecast.",
    no_args_is_help=False,
    add_completion=True,
)

TimeoutOption = Annotated[
    float, typer.Option("--timeout", "-t", help="Seconds to wait for mDNS discovery.")
]


def _discover_or_exit(timeout: float) -> list[discovery.CastDevice]:
    with ui.console.status("[bold]Searching for Cast devices…[/bold]"):
        devices = discovery.discover(timeout=timeout)
    if not devices:
        ui.no_devices_help()
        raise typer.Exit(code=1)
    return devices


def _version_callback(value: bool) -> None:
    if value:
        ui.console.print(f"ubuntu-cast {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True)
    ] = False,
) -> None:
    """With no subcommand: discover devices, pick one interactively, and start casting."""
    if ctx.invoked_subcommand is not None:
        return
    devices = _discover_or_exit(timeout=5.0)
    device = ui.pick_device(devices)
    _start_casting(device)


@app.command()
def devices(timeout: TimeoutOption = 5.0) -> None:
    """List Cast devices on the local network."""
    found = _discover_or_exit(timeout)
    ui.console.print(ui.device_table(found))


@app.command()
def start(
    device: Annotated[
        str, typer.Option("--device", "-d", help="Device name (exact or unique prefix).")
    ],
    timeout: TimeoutOption = 5.0,
) -> None:
    """Start casting to a named device (non-interactive, scriptable)."""
    found = _discover_or_exit(timeout)
    match = discovery.find_device(found, device)
    if match is None:
        ui.error_console.print(f"No device matching '{device}'.")
        ui.console.print(ui.device_table(found))
        raise typer.Exit(code=1)
    _start_casting(match)


@app.command(name="doctor")
def doctor_command() -> None:
    """Check that this machine is ready to cast (portal, PipeWire, encoders)."""
    results = doctor.run_all_checks()
    ui.console.print(ui.doctor_table(results))
    if any(r.status is doctor.Status.FAIL for r in results):
        ui.error_console.print("Some checks failed — casting won't work until they're fixed.")
        raise typer.Exit(code=1)
    ui.console.print("[green]Ready to cast.[/green]")


def _start_casting(device: discovery.CastDevice) -> None:
    ui.console.print(
        f"Selected [bold cyan]{device.name}[/bold cyan] [dim]({device.model}, {device.host})[/dim]"
    )
    ui.console.print(
        "[yellow]Screen mirroring isn't implemented yet — it lands in Phase 3 "
        "(see INTENT.md). Discovery and device selection are working.[/yellow]"
    )


def main() -> None:
    app()
