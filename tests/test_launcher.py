import pytest

from ubuntu_cast import launcher


def test_desktop_entry_opens_a_terminal_for_the_picker_and_panel():
    entry = launcher.desktop_entry("/opt/bin/ubuntu-cast")
    assert "Exec=/opt/bin/ubuntu-cast\n" in entry
    assert "Terminal=true" in entry
    assert "Name=Ubuntu Cast" in entry


def test_desktop_entry_offers_an_audio_only_action():
    entry = launcher.desktop_entry("/opt/bin/ubuntu-cast")
    assert "Actions=audio-only;" in entry
    assert "Exec=/opt/bin/ubuntu-cast --audio-only" in entry


def test_install_writes_the_launcher_file(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "find_executable", lambda: "/opt/bin/ubuntu-cast")
    path = launcher.install(directory=tmp_path / "applications")
    assert path.name == "ubuntu-cast.desktop"
    assert "Exec=/opt/bin/ubuntu-cast" in path.read_text()


def test_find_executable_errors_when_not_installed(monkeypatch):
    monkeypatch.setattr(launcher.sys, "argv", ["pytest"])
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="uv tool install"):
        launcher.find_executable()
