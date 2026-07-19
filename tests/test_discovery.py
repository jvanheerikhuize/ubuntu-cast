from ubuntu_cast.discovery import CastDevice, find_device


def _device(name: str) -> CastDevice:
    return CastDevice(name=name, model="Chromecast", host="192.168.1.10", port=8009, uuid="u")


DEVICES = [_device("Bedroom speaker"), _device("Living Room TV"), _device("Living Room speaker")]


def test_exact_match_wins():
    assert find_device(DEVICES, "Living Room TV").name == "Living Room TV"


def test_unique_prefix_matches_case_insensitively():
    assert find_device(DEVICES, "bed").name == "Bedroom speaker"


def test_ambiguous_prefix_returns_none():
    assert find_device(DEVICES, "Living") is None


def test_no_match_returns_none():
    assert find_device(DEVICES, "Kitchen") is None
