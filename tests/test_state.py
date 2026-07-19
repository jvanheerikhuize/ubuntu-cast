import pytest

from ubuntu_cast import state


@pytest.fixture(autouse=True)
def state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path


def test_load_returns_none_when_nothing_saved():
    assert state.load_restore_token() is None


def test_save_then_load_round_trips():
    state.save_restore_token("tok-123")
    assert state.load_restore_token() == "tok-123"


def test_save_none_keeps_the_existing_token():
    state.save_restore_token("tok-123")
    state.save_restore_token(None)
    assert state.load_restore_token() == "tok-123"


def test_blank_file_reads_as_no_token(state_home):
    directory = state_home / "ubuntu-cast"
    directory.mkdir()
    (directory / "restore-token").write_text("\n")
    assert state.load_restore_token() is None


def test_load_last_device_returns_none_when_nothing_saved():
    assert state.load_last_device() is None


def test_save_then_load_last_device_round_trips():
    state.save_last_device("woonkamer TV", False)
    assert state.load_last_device() == ("woonkamer TV", False)


def test_save_then_load_last_device_remembers_audio_only():
    state.save_last_device("woonkamer speaker", True)
    assert state.load_last_device() == ("woonkamer speaker", True)


def test_save_last_device_overwrites_previous_value():
    state.save_last_device("woonkamer TV", False)
    state.save_last_device("keuken TV", True)
    assert state.load_last_device() == ("keuken TV", True)
