from ubuntu_cast import doctor
from ubuntu_cast.doctor import Status


def test_wayland_session_is_ok(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert doctor.check_session().status is Status.OK


def test_x11_session_warns(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    result = doctor.check_session()
    assert result.status is Status.WARN
    assert result.hint


def test_missing_session_fails_with_hint(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    result = doctor.check_session()
    assert result.status is Status.FAIL
    assert result.hint


def test_missing_gstreamer_has_install_hint(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    result = doctor.check_gstreamer()
    assert result.status is Status.FAIL
    assert "apt install" in result.hint


def test_every_check_runs():
    results = doctor.run_all_checks()
    assert len(results) == 9
    assert all(r.label and r.detail for r in results)
