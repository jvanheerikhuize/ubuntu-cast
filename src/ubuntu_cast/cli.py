"""The ubuntu-cast command-line interface."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from . import __version__, discovery, doctor, session, ui

app = typer.Typer(
    name="ubuntu-cast",
    help="Cast your Ubuntu desktop — screen and audio — to a Chromecast.",
    no_args_is_help=False,
    add_completion=True,
)

TimeoutOption = Annotated[
    float, typer.Option("--timeout", "-t", help="Seconds to wait for mDNS discovery.")
]

AudioOnlyOption = Annotated[
    bool, typer.Option("--audio-only", help="Cast desktop audio without the screen.")
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
    audio_only: AudioOnlyOption = False,
) -> None:
    """With no subcommand: discover devices, pick one interactively, and start casting."""
    if ctx.invoked_subcommand is not None:
        return
    devices = _discover_or_exit(timeout=5.0)
    device = ui.pick_device(devices)
    _start_casting(device, audio_only=audio_only)


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
    audio_only: AudioOnlyOption = False,
) -> None:
    """Start casting to a named device (non-interactive, scriptable)."""
    found = _discover_or_exit(timeout)
    match = discovery.find_device(found, device)
    if match is None:
        ui.error_console.print(f"No device matching '{device}'.")
        ui.console.print(ui.device_table(found))
        raise typer.Exit(code=1)
    _start_casting(match, audio_only=audio_only)


@app.command(name="doctor")
def doctor_command() -> None:
    """Check that this machine is ready to cast (portal, PipeWire, encoders)."""
    results = doctor.run_all_checks()
    ui.console.print(ui.doctor_table(results))
    if any(r.status is doctor.Status.FAIL for r in results):
        ui.error_console.print("Some checks failed — casting won't work until they're fixed.")
        raise typer.Exit(code=1)
    ui.console.print("[green]Ready to cast.[/green]")


def _start_casting(device: discovery.CastDevice, audio_only: bool = False) -> None:
    ui.console.print(
        f"Selected [bold cyan]{device.name}[/bold cyan] [dim]({device.model}, {device.host})[/dim]"
    )
    if audio_only:
        _run_session(
            session.AudioSession(device),
            device,
            spinner=f"Connecting to {device.name}…",
            banner="♪ Casting desktop audio",
        )
        return
    ui.console.print("[dim]Approve screen sharing in the system dialog (pick a screen).[/dim]")
    _run_session(
        session.ScreenSession(device),
        device,
        spinner=f"Waiting for approval, then connecting to {device.name}…",
        banner="⛶ Casting your screen",
    )


def _run_session(
    cast_session: session.AudioSession | session.ScreenSession,
    device: discovery.CastDevice,
    spinner: str,
    banner: str,
) -> None:
    try:
        with ui.console.status(f"[bold]{spinner}[/bold]"):
            url = cast_session.start()
    except Exception as error:
        cast_session.stop()
        ui.error_console.print(f"Could not start casting: {error}")
        raise typer.Exit(code=1) from error
    ui.console.print(
        f"[green]{banner}[/green] to [bold cyan]{device.name}[/bold cyan] [dim]({url})[/dim]"
    )
    ui.console.print("[dim]Press Ctrl+C to stop.[/dim]")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        with ui.console.status("[bold]Stopping…[/bold]"):
            cast_session.stop()
        ui.console.print("Stopped.")


def main() -> None:
    app()
