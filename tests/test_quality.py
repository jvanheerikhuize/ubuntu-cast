import pytest

from ubuntu_cast import quality


def test_default_is_the_balanced_preset():
    assert quality.DEFAULT is quality.PRESETS["balanced"]


def test_balanced_matches_the_values_the_pipeline_used_before_presets():
    balanced = quality.PRESETS["balanced"]
    assert balanced.resolution == (1920, 1080)
    assert balanced.fps == 30
    assert balanced.video_bitrate == 8000


def test_low_is_cheaper_than_high_on_every_axis():
    low, high = quality.PRESETS["low"], quality.PRESETS["high"]
    assert low.fps < high.fps
    assert low.video_bitrate < high.video_bitrate
    assert low.audio_bitrate < high.audio_bitrate


def test_high_stops_at_1080p_because_thats_the_receivers_ceiling():
    assert quality.PRESETS["high"].resolution == (1920, 1080)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("720p", (1280, 720)),
        ("1080p", (1920, 1080)),
        ("1600x900", (1600, 900)),
        ("  1080P  ", (1920, 1080)),
    ],
)
def test_parse_resolution_accepts_names_and_explicit_sizes(text, expected):
    assert quality.parse_resolution(text) == expected


def test_parse_resolution_maps_native_to_no_scaling():
    assert quality.parse_resolution("native") is None


@pytest.mark.parametrize("text", ["", "huge", "1920x", "0x0", "axb", "-100x200"])
def test_parse_resolution_rejects_nonsense(text):
    with pytest.raises(ValueError):
        quality.parse_resolution(text)


def test_resolve_without_overrides_returns_the_preset():
    assert quality.resolve("high") == quality.PRESETS["high"]


def test_resolve_lets_each_flag_override_the_preset():
    settings = quality.resolve("low", resolution="1080p", fps=60, video_bitrate=9000)
    assert settings.resolution == (1920, 1080)
    assert settings.fps == 60
    assert settings.video_bitrate == 9000
    # Untouched fields still come from the preset.
    assert settings.audio_bitrate == quality.PRESETS["low"].audio_bitrate


def test_resolve_carries_hardware_and_cursor_flags():
    settings = quality.resolve("balanced", hardware=False, show_cursor=False)
    assert settings.hardware is False
    assert settings.show_cursor is False


def test_resolve_rejects_an_unknown_preset():
    with pytest.raises(ValueError, match="unknown quality"):
        quality.resolve("cinematic")


@pytest.mark.parametrize(
    "kwargs", [{"fps": 0}, {"fps": -1}, {"video_bitrate": 0}, {"audio_bitrate": -5}]
)
def test_resolve_rejects_non_positive_numbers(kwargs):
    with pytest.raises(ValueError):
        quality.resolve("balanced", **kwargs)


def test_label_summarises_the_settings():
    assert quality.PRESETS["balanced"].label == "1080p · 30 fps · 8.0 Mb/s"


def test_label_says_native_when_there_is_no_scaling():
    assert quality.resolve("balanced", resolution="native").label.startswith("native")
