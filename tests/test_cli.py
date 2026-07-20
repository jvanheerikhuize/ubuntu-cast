import signal

import pytest
from typer.testing import CliRunner

from ubuntu_cast import cli, state

runner = CliRunner()


@pytest.fixture(autouse=True)
def state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def signals(monkeypatch):
    """Capture what `stop` would have signalled instead of signalling it.

    Signal 0 is the liveness probe in state._process_alive, not a stop — pass it
    through to the real os.kill so the session still looks like it's running.
    """
    real_kill = cli.os.kill
    sent: list[tuple[int, int]] = []

    def fake_kill(pid, sig):
        if sig == 0:
            return real_kill(pid, sig)
        sent.append((pid, sig))
        return None

    monkeypatch.setattr(cli.os, "kill", fake_kill)
    return sent


def test_stop_says_so_when_nothing_is_casting():
    result = runner.invoke(cli.app, ["stop"])
    assert result.exit_code == 0
    assert "Nothing is casting" in result.stdout


def test_stop_interrupts_a_terminal_cast(signals):
    state.save_session("woonkamer TV", False, stop_signal=signal.SIGINT)
    result = runner.invoke(cli.app, ["stop"])
    assert result.exit_code == 0
    assert [sig for _pid, sig in signals] == [signal.SIGINT]
    assert "woonkamer TV" in result.stdout


def test_stop_uses_sigusr1_so_a_tray_cast_ends_without_killing_the_tray(signals):
    state.save_session("woonkamer TV", False, stop_signal=signal.SIGUSR1)
    runner.invoke(cli.app, ["stop"])
    assert [sig for _pid, sig in signals] == [signal.SIGUSR1]


def test_stop_forgets_the_record_when_the_process_vanished(monkeypatch, state_home):
    """The process can die between the liveness check and the signal."""
    state.save_session("woonkamer TV", False)
    real_kill = cli.os.kill

    def gone(pid, sig):
        if sig == 0:  # the liveness probe still succeeds
            return real_kill(pid, sig)
        raise ProcessLookupError("No such process")

    monkeypatch.setattr(cli.os, "kill", gone)
    result = runner.invoke(cli.app, ["stop"])
    assert result.exit_code == 1
    assert not (state_home / "ubuntu-cast" / "session.json").exists()


@pytest.mark.parametrize(
    "flags",
    [
        ["--quality", "cinematic"],
        ["--resolution", "enormous"],
        ["--fps", "0"],
        ["--bitrate", "-1"],
    ],
)
def test_bad_quality_flags_fail_before_discovery_runs(flags, monkeypatch):
    """Nonsense settings should be rejected immediately, not after an mDNS wait."""

    def unexpected(*args, **kwargs):
        raise AssertionError("discovery should not run for invalid flags")

    monkeypatch.setattr(cli, "_discover_or_exit", unexpected)
    result = runner.invoke(cli.app, ["start", "--device", "TV", *flags])
    assert result.exit_code == 2
