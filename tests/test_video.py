import pytest

from ubuntu_cast import quality, video


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


def test_no_hw_skips_the_vaapi_encoder_even_when_it_is_installed(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available("vaapih264enc", "x264enc"))
    encoder = video.pick_h264_encoder(quality.resolve("balanced", hardware=False))
    assert encoder[0] == "x264enc"


def test_no_hw_error_points_at_the_flag_rather_than_vaapi(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available())
    with pytest.raises(RuntimeError, match="--no-hw"):
        video.pick_h264_encoder(quality.resolve("balanced", hardware=False))


def test_encoder_carries_the_requested_bitrate_and_keyframe_interval(monkeypatch):
    monkeypatch.setattr(video, "_have_element", _available("x264enc"))
    encoder = video.pick_h264_encoder(quality.resolve("balanced", fps=60, video_bitrate=12000))
    assert "bitrate=12000" in encoder
    # Keyframes every two seconds — at 60 fps that's every 120 frames.
    assert "key-int-max=120" in encoder


def test_caps_carry_the_requested_resolution_and_framerate():
    settings = quality.resolve("balanced", resolution="720p", fps=24)
    command = video.fmp4_stream_command(7, 42, "m", ["x264enc"], ["avenc_aac"], settings)
    caps = command[command.index("videorate") + 2]
    assert "framerate=24/1" in caps
    assert "width=1280" in caps
    assert "height=720" in caps


def test_a_resolution_adds_letterboxed_scaling_before_the_rate_conversion():
    command = video.fmp4_stream_command(
        7, 42, "m", ["x264enc"], ["avenc_aac"], quality.resolve("balanced", resolution="720p")
    )
    assert "videoscale" in command
    assert "add-borders=true" in command
    assert command.index("videoscale") < command.index("videorate")


def test_native_resolution_leaves_the_frames_unscaled():
    command = video.fmp4_stream_command(
        7, 42, "m", ["x264enc"], ["avenc_aac"], quality.resolve("balanced", resolution="native")
    )
    assert "videoscale" not in command
    caps = command[command.index("videorate") + 2]
    assert "width=" not in caps
