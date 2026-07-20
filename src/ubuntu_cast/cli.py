"""The ubuntu-cast command-line interface."""

from __future__ import annotations

import os
import signal
import time
from typing import Annotated

import typer
from rich.live import Live

from . import __version__, discovery, doctor, launcher, quality, session, state, tray, ui

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

QualityOption = Annotated[
    str, typer.Option("--quality", "-q", help="Preset: low, balanced, or high.")
]
ResolutionOption = Annotated[
    str | None,
    typer.Option("--resolution", help="720p, 1080p, native, or WIDTHxHEIGHT."),
]
FpsOption = Annotated[int | None, typer.Option("--fps", help="Frames per second.")]
BitrateOption = Annotated[
    int | None, typer.Option("--bitrate", help="Video bitrate in kbit/s.")
]
AudioBitrateOption = Annotated[
    int | None, typer.Option("--audio-bitrate", help="Audio bitrate in kbit/s.")
]
HardwareOption = Annotated[
    bool, typer.Option("--hw/--no-hw", help="Allow VA-API hardware encoding.")
]
NoCursorOption = Annotated[
    bool, typer.Option("--no-cursor", help="Hide the mouse pointer in the capture.")
]


def _quality_or_exit(
    preset: str,
    resolution: str | None,
    fps: int | None,
    bitrate: int | None,
    audio_bitrate: int | None,
    hardware: bool,
    no_cursor: bool,
) -> quality.Quality:
    """Turn the quality flags into a Quality, or exit with the reason why not."""
    try:
        return quality.resolve(
            preset,
            resolution=resolution,
            fps=fps,
            video_bitrate=bitrate,
            audio_bitrate=audio_bitrate,
            hardware=hardware,
            show_cursor=not no_cursor,
        )
    except ValueError as error:
        ui.error_console.print(str(error))
        raise typer.Exit(code=2) from error


def _discover_or_exit(timeout: float, wanted: str | None = None) -> list[discovery.CastDevice]:
    with ui.console.status("[bold]Searching for Cast devices…[/bold]"):
        devices = discovery.discover(timeout=timeout, wanted=wanted)
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
    """With no subcommand: show the tray icon (falls back to the terminal picker)."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        tray.run()
    except RuntimeError:
        _pick_and_cast(audio_only=audio_only)


def _pick_and_cast(audio_only: bool, settings: quality.Quality = quality.DEFAULT) -> None:
    devices = _discover_or_exit(timeout=5.0)
    device = ui.pick_device(devices)
    _start_casting(device, audio_only=audio_only, settings=settings)


@app.command(name="pick")
def pick_command(
    audio_only: AudioOnlyOption = False,
    quality_preset: QualityOption = "balanced",
    resolution: ResolutionOption = None,
    fps: FpsOption = None,
    bitrate: BitrateOption = None,
    audio_bitrate: AudioBitrateOption = None,
    hardware: HardwareOption = True,
    no_cursor: NoCursorOption = False,
) -> None:
    """Discover devices, pick one interactively in the terminal, and start casting."""
    settings = _quality_or_exit(
        quality_preset, resolution, fps, bitrate, audio_bitrate, hardware, no_cursor
    )
    _pick_and_cast(audio_only=audio_only, settings=settings)


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
    quality_preset: QualityOption = "balanced",
    resolution: ResolutionOption = None,
    fps: FpsOption = None,
    bitrate: BitrateOption = None,
    audio_bitrate: AudioBitrateOption = None,
    hardware: HardwareOption = True,
    no_cursor: NoCursorOption = False,
) -> None:
    """Start casting to a named device (non-interactive, scriptable)."""
    settings = _quality_or_exit(
        quality_preset, resolution, fps, bitrate, audio_bitrate, hardware, no_cursor
    )
    # An exact name match lets discovery return the moment the device appears.
    found = _discover_or_exit(timeout, wanted=device)
    match = discovery.find_device(found, device)
    if match is None:
        ui.error_console.print(f"No device matching '{device}'.")
        ui.console.print(ui.device_table(found))
        raise typer.Exit(code=1)
    _start_casting(match, audio_only=audio_only, settings=settings)


@app.command(name="stop")
def stop_command() -> None:
    """Stop the cast running in another terminal or in the tray icon."""
    record = state.load_session()
    if record is None:
        ui.console.print("Nothing is casting right now.")
        return
    try:
        os.kill(record["pid"], record.get("stop_signal", signal.SIGINT))
    except OSError as error:
        # The process vanished between the liveness check and the signal.
        state.clear_session()
        ui.error_console.print(f"Could not stop the cast: {error}")
        raise typer.Exit(code=1) from error
    ui.console.print(f"Stopping the cast to [bold cyan]{record.get('device', '?')}[/bold cyan].")


@app.command(name="install-launcher")
def install_launcher() -> None:
    """Add an "Ubuntu Cast" launcher to the GNOME app grid."""
    try:
        path = launcher.install()
    except RuntimeError as error:
        ui.error_console.print(f"Could not install the launcher: {error}")
        raise typer.Exit(code=1) from error
    ui.console.print(f"Launcher installed at [bold]{path}[/bold].")
    ui.console.print(
        "Search for [bold cyan]Ubuntu Cast[/bold cyan] in the Activities overview "
        "(right-click it for audio-only)."
    )


@app.command(name="install-autostart")
def install_autostart_command() -> None:
    """Start the tray icon automatically at login."""
    try:
        path = launcher.install_autostart()
    except RuntimeError as error:
        ui.error_console.print(f"Could not install autostart: {error}")
        raise typer.Exit(code=1) from error
    ui.console.print(f"Autostart entry installed at [bold]{path}[/bold].")
    ui.console.print("The tray icon will now appear automatically the next time you log in.")


@app.command(name="tray")
def tray_command(
    timeout: TimeoutOption = 5.0,
) -> None:
    """Show a GNOME top-bar icon to start/stop casting without a terminal."""
    try:
        tray.run(timeout=timeout)
    except RuntimeError as error:
        ui.error_console.print(f"Could not start the tray: {error}")
        raise typer.Exit(code=1) from error


@app.command(name="doctor")
def doctor_command() -> None:
    """Check that this machine is ready to cast (portal, PipeWire, encoders)."""
    results = doctor.run_all_checks()
    ui.console.print(ui.doctor_table(results))
    if any(r.status is doctor.Status.FAIL for r in results):
        ui.error_console.print("Some checks failed — casting won't work until they're fixed.")
        raise typer.Exit(code=1)
    ui.console.print("[green]Ready to cast.[/green]")


def _start_casting(
    device: discovery.CastDevice,
    audio_only: bool = False,
    settings: quality.Quality = quality.DEFAULT,
) -> None:
    ui.console.print(
        f"Selected [bold cyan]{device.name}[/bold cyan] [dim]({device.model}, {device.host})[/dim]"
    )
    if audio_only:
        _run_session(
            session.AudioSession(device, settings),
            device,
            spinner=f"Connecting to {device.name}…",
            banner="♪ Casting desktop audio",
            audio_only=True,
        )
        return
    ui.console.print(f"[dim]Quality: {settings.label}[/dim]")
    if state.load_restore_token() is None:
        ui.console.print("[dim]Approve screen sharing in the system dialog (pick a screen).[/dim]")
    _run_session(
        session.ScreenSession(device, settings),
        device,
        spinner=f"Waiting for approval, then connecting to {device.name}…",
        banner="⛶ Casting your screen",
    )


def _run_session(
    cast_session: session.AudioSession | session.ScreenSession,
    device: discovery.CastDevice,
    spinner: str,
    banner: str,
    audio_only: bool = False,
) -> None:
    try:
        with ui.console.status(f"[bold]{spinner}[/bold]"):
            url = cast_session.start()
    except Exception as error:
        cast_session.stop()
        ui.error_console.print(f"Could not start casting: {error}")
        raise typer.Exit(code=1) from error
    started = time.monotonic()
    # SIGINT lands in the same place Ctrl+C does, so `ubuntu-cast stop` reuses
    # the cleanup path below rather than needing one of its own.
    state.save_session(device.name, audio_only, url=url, stop_signal=signal.SIGINT)
    try:
        with Live(console=ui.console, transient=True, refresh_per_second=4) as live:
            while True:
                live.update(
                    ui.casting_panel(
                        device,
                        url,
                        title=banner,
                        elapsed_seconds=time.monotonic() - started,
                        viewers=cast_session.active_streams,
                    )
                )
                time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        state.clear_session()
        with ui.console.status("[bold]Stopping…[/bold]"):
            cast_session.stop()
        elapsed = ui.format_elapsed(time.monotonic() - started)
        ui.console.print(f"Stopped after [bold]{elapsed}[/bold].")


def main() -> None:
    app()
