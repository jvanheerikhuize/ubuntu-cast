"""Rich-based terminal output: tables, pickers, and status messages."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import IntPrompt
from rich.table import Table

from .discovery import CastDevice
from .doctor import CheckResult, Status

console = Console()
error_console = Console(stderr=True, style="bold red")

_STATUS_MARKS = {
    Status.OK: "[green]✔[/green]",
    Status.WARN: "[yellow]⚠[/yellow]",
    Status.FAIL: "[red]✘[/red]",
}


def device_table(devices: list[CastDevice]) -> Table:
    table = Table(title=f"Cast devices ({len(devices)} found)", title_justify="left")
    table.add_column("Name", style="bold cyan")
    table.add_column("Model")
    table.add_column("Address", style="dim")
    for device in devices:
        table.add_row(device.name, device.model, f"{device.host}:{device.port}")
    return table


def pick_device(devices: list[CastDevice]) -> CastDevice:
    """Numbered interactive picker; returns the chosen device."""
    if len(devices) == 1:
        console.print(f"Using the only device found: [bold cyan]{devices[0].name}[/bold cyan]")
        return devices[0]
    for index, device in enumerate(devices, start=1):
        console.print(
            f"  [bold]{index}[/bold]  [cyan]{device.name}[/cyan]  [dim]{device.model}[/dim]"
        )
    choice = IntPrompt.ask(
        "Cast to",
        choices=[str(i) for i in range(1, len(devices) + 1)],
        show_choices=False,
    )
    return devices[choice - 1]


def doctor_table(results: list[CheckResult]) -> Table:
    table = Table(title="Environment check", title_justify="left")
    table.add_column("")
    table.add_column("Check", style="bold")
    table.add_column("Result")
    table.add_column("Hint", style="dim", max_width=60)
    for result in results:
        table.add_row(_STATUS_MARKS[result.status], result.label, result.detail, result.hint)
    return table


def no_devices_help() -> None:
    error_console.print("No Cast devices found.")
    console.print(
        "[dim]Chromecasts announce themselves over mDNS on the local network. Check that:\n"
        "  • this machine and the Chromecast are on the same network/VLAN\n"
        "  • mDNS (UDP 5353) isn't blocked by a firewall\n"
        "  • the device is powered on — try casting to it from another app\n"
        "Then retry, or increase the wait: ubuntu-cast devices --timeout 10[/dim]"
    )
