from rich.console import Console

from ubuntu_cast import ui
from ubuntu_cast.discovery import CastDevice

DEVICE = CastDevice(
    name="Living Room TV", model="Chromecast", host="192.168.1.10", port=8009, uuid="u"
)


def _render(renderable) -> str:
    console = Console(record=True, width=100)
    console.print(renderable)
    return console.export_text()


def test_format_elapsed_wall_clock_style():
    assert ui.format_elapsed(0) == "00:00"
    assert ui.format_elapsed(247) == "04:07"
    assert ui.format_elapsed(3600 + 4 * 60 + 7) == "1:04:07"


def test_casting_panel_shows_waiting_before_any_client_connects():
    text = _render(
        ui.casting_panel(
            DEVICE, "http://10.0.0.1:8010/stream", "⛶ Casting", elapsed_seconds=3, viewers=0
        )
    )
    assert "Living Room TV" in text
    assert "http://10.0.0.1:8010/stream" in text
    assert "waiting" in text
    assert "00:03" in text


def test_casting_panel_shows_streaming_once_a_client_connects():
    text = _render(
        ui.casting_panel(
            DEVICE, "http://10.0.0.1:8010/stream", "⛶ Casting", elapsed_seconds=65, viewers=1
        )
    )
    assert "streaming" in text
    assert "01:05" in text
