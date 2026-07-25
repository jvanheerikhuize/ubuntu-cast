import json
import signal

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


def test_load_session_returns_none_when_nothing_is_casting():
    assert state.load_session() is None


def test_save_then_load_session_round_trips():
    state.save_session("woonkamer TV", False, url="http://host/stream")
    record = state.load_session()
    assert record["device"] == "woonkamer TV"
    assert record["audio_only"] is False
    assert record["url"] == "http://host/stream"
    assert record["stop_signal"] == signal.SIGINT


def test_save_session_records_this_process_by_default():
    import os

    state.save_session("woonkamer TV", False)
    assert state.load_session()["pid"] == os.getpid()


def test_save_session_keeps_the_trays_stop_signal():
    state.save_session("woonkamer TV", True, stop_signal=signal.SIGUSR1)
    assert state.load_session()["stop_signal"] == signal.SIGUSR1


def test_clear_session_forgets_the_record():
    state.save_session("woonkamer TV", False)
    state.clear_session()
    assert state.load_session() is None


def test_clear_session_is_safe_when_nothing_was_recorded():
    state.clear_session()  # must not raise


def test_load_session_clears_a_record_whose_process_is_gone(state_home, monkeypatch):
    state.save_session("woonkamer TV", False)
    monkeypatch.setattr(state, "_process_alive", lambda pid, cmdline=None: False)
    assert state.load_session() is None
    assert not (state_home / "ubuntu-cast" / "session.json").exists()


def test_load_session_rejects_a_recycled_pid(state_home):
    """A live pid running something else must not be signalled."""
    state.save_session("woonkamer TV", False)
    path = state_home / "ubuntu-cast" / "session.json"
    record = json.loads(path.read_text())
    record["cmdline"] = "/usr/bin/something-else\x00"
    path.write_text(json.dumps(record))
    assert state.load_session() is None


def test_process_alive_trusts_liveness_when_there_is_no_fingerprint():
    import os

    assert state._process_alive(os.getpid()) is True


def test_load_session_ignores_a_corrupt_record(state_home):
    directory = state_home / "ubuntu-cast"
    directory.mkdir()
    (directory / "session.json").write_text("not json{")
    assert state.load_session() is None


def test_load_session_ignores_a_record_without_a_pid(state_home):
    directory = state_home / "ubuntu-cast"
    directory.mkdir()
    (directory / "session.json").write_text(json.dumps({"device": "TV"}))
    assert state.load_session() is None


def test_process_alive_says_no_for_a_pid_that_cannot_exist():
    assert state._process_alive(2**31 - 1) is False
