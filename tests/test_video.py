import pytest

from ubuntu_cast import video


def _available(*names: str):
    return lambda element: element in names


def test_pick_h264_encoder_prefers_hardware(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available("vaapih264enc", "x264enc"))
    assert video.pick_h264_encoder()[0] == "vaapih264enc"


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
    assert command.count("queue") == 2
