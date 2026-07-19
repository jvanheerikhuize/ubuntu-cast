import pytest

from ubuntu_cast import video


def _available(*names: str):
    return lambda element: element in names


def test_pick_h264_encoder_prefers_hardware(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available("vaapih264enc", "x264enc"))
    encoder = video.pick_h264_encoder()
    assert encoder[0] == "vaapih264enc"
    # Intel's iHD driver fails caps negotiation in cbr/vbr modes; the encoder
    # must stay on its default rate control.
    assert not any(arg.startswith("rate-control=") for arg in encoder)


def test_pick_h264_encoder_falls_back_to_x264(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available("x264enc"))
    encoder = video.pick_h264_encoder()
    assert encoder[0] == "x264enc"
    assert "tune=zerolatency" in encoder


def test_pick_h264_encoder_errors_with_install_hint(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available())
    with pytest.raises(RuntimeError, match="gstreamer1.0-vaapi"):
        video.pick_h264_encoder()


def test_pick_aac_encoder_scales_bitrate_to_bps(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available("avenc_aac"))
    assert video.pick_aac_encoder(192) == ["avenc_aac", "bitrate=192000"]


def test_pick_aac_encoder_errors_with_install_hint(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available())
    with pytest.raises(RuntimeError, match="gstreamer1.0-libav"):
        video.pick_aac_encoder()


def test_fmp4_stream_command_wires_both_branches_into_the_mux():
    command = video.fmp4_stream_command(
        7, 42, "sink.monitor", ["x264enc", "bitrate=8000"], ["avenc_aac", "bitrate=192000"]
    )
    assert command[0] == "gst-launch-1.0"
    assert "fd=7" in command
    assert "path=42" in command
    assert "device=sink.monitor" in command
    # The named mux must be defined before the audio branch references "mux."
    assert command.index("name=mux") < command.index("mux.")
    assert "streamable=true" in command
    assert command[-1] == "mux."
    assert "fd=1" in command
    # Capture-decoupling queue plus one on each live branch before the mux.
    assert command.count("queue") == 3


def test_fmp4_stream_command_decouples_capture_from_encoding():
    command = video.fmp4_stream_command(7, 42, "m", ["x264enc"], ["avenc_aac"])
    # A queue right after pipewiresrc keeps a slow encoder from
    # back-pressuring the capture into dropping portal frames.
    assert command[command.index("do-timestamp=true") + 2] == "queue"
    # videoconvert should use one thread per CPU, not a single thread.
    assert command[command.index("videoconvert") + 1] == "n-threads=0"


def test_fmp4_stream_command_pins_a_constant_framerate():
    # The portal stream is variable-rate (framerate=0/1), which vaapih264enc
    # refuses to negotiate; videorate + the caps filter make it constant.
    command = video.fmp4_stream_command(7, 42, "m", ["x264enc"], ["avenc_aac"])
    assert "videorate" in command
    caps = command[command.index("videorate") + 2]
    assert "framerate=30/1" in caps
    assert command.index("videorate") < command.index("x264enc")
