import subprocess

import pytest

from ubuntu_cast import audio


def _fake_pactl(stdout: str):
    def run(cmd, **kwargs):
        assert cmd == ["pactl", "get-default-sink"]
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    return run


def test_default_sink_monitor_appends_monitor_suffix(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_pactl("alsa_output.pci.analog-stereo\n"))
    assert audio.default_sink_monitor() == "alsa_output.pci.analog-stereo.monitor"


def test_default_sink_monitor_rejects_empty_output(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_pactl("\n"))
    with pytest.raises(RuntimeError):
        audio.default_sink_monitor()


def test_mp3_stream_command_targets_requested_bitrate():
    command = audio.mp3_stream_command("sink.monitor", bitrate=256)
    assert command[0] == "gst-launch-1.0"
    assert "device=sink.monitor" in command
    assert "bitrate=256" in command
    assert "lamemp3enc" in command
    assert command[-1] == "fd=1"
