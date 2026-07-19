import sys
import types

import pytest

from ubuntu_cast import tray
from ubuntu_cast.discovery import CastDevice

DEVICE = CastDevice(
    name="woonkamer TV", model="Chromecast", host="192.168.178.96", port=8009, uuid="u1"
)


def test_ensure_gi_does_nothing_when_gi_already_importable(monkeypatch):
    monkeypatch.setitem(sys.modules, "gi", types.SimpleNamespace())
    clean_path = [p for p in sys.path if p != str(tray.SYSTEM_DIST_PACKAGES)]
    monkeypatch.setattr(sys, "path", clean_path)
    tray._ensure_gi()
    assert str(tray.SYSTEM_DIST_PACKAGES) not in sys.path


def test_ensure_gi_adds_system_dist_packages_when_gi_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "gi", None)  # forces ImportError on `import gi`
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(tray.SYSTEM_DIST_PACKAGES)])

    real_import = __import__
    attempts = {"count": 0}

    def fake_import(name, *args, **kwargs):
        if name == "gi":
            attempts["count"] += 1
            if str(tray.SYSTEM_DIST_PACKAGES) in sys.path:
                monkeypatch.setitem(sys.modules, "gi", types.SimpleNamespace())
                return sys.modules["gi"]
            raise ImportError("no module named gi")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    tray._ensure_gi()
    assert str(tray.SYSTEM_DIST_PACKAGES) in sys.path
    assert attempts["count"] == 2


def test_ensure_gi_raises_with_apt_hint_when_still_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "gi", None)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "gi":
            raise ImportError("no module named gi")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    with pytest.raises(RuntimeError, match="python3-gi"):
        tray._ensure_gi()


def test_find_appindicator_namespace_returns_none_when_no_typelib(monkeypatch):
    monkeypatch.setattr(tray, "_ensure_gi", lambda: None)
    fake_gi = types.SimpleNamespace(require_version=lambda *a: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setitem(sys.modules, "gi", fake_gi)
    assert tray.find_appindicator_namespace() is None


def test_find_appindicator_namespace_prefers_ayatana(monkeypatch):
    monkeypatch.setattr(tray, "_ensure_gi", lambda: None)
    seen = []

    def require_version(namespace, _version):
        seen.append(namespace)
        if namespace != "AyatanaAppIndicator3":
            raise ValueError("not available")

    fake_gi = types.SimpleNamespace(require_version=require_version)
    monkeypatch.setitem(sys.modules, "gi", fake_gi)
    monkeypatch.setitem(sys.modules, "gi.repository.AyatanaAppIndicator3", types.SimpleNamespace())
    assert tray.find_appindicator_namespace() == "AyatanaAppIndicator3"
    assert seen[0] == "AyatanaAppIndicator3"


class FakeMenuItem:
    def __init__(self, label=""):
        self.label = label
        self.sensitive = True
        self.handlers = []

    def connect(self, _signal, handler, *args):
        self.handlers.append((handler, args))

    def set_sensitive(self, value):
        self.sensitive = value

    def activate(self):
        for handler, args in self.handlers:
            handler(self, *args)


class FakeSeparator(FakeMenuItem):
    pass


class FakeMenu:
    def __init__(self):
        self.children = []

    def append(self, item):
        self.children.append(item)

    def get_children(self):
        return list(self.children)

    def remove(self, item):
        self.children.remove(item)

    def show_all(self):
        pass


class FakeGtk:
    MenuItem = FakeMenuItem
    SeparatorMenuItem = FakeSeparator
    Menu = FakeMenu

    def main_quit(self):
        self.quit_called = True


class FakeIndicator:
    def __init__(self):
        self.menu = None

    def set_menu(self, menu):
        self.menu = menu

    def set_status(self, _status):
        pass


class FakeIndicatorModule:
    IndicatorCategory = types.SimpleNamespace(APPLICATION_STATUS="app")
    IndicatorStatus = types.SimpleNamespace(ACTIVE="active")

    class Indicator:
        @staticmethod
        def new(_id, _icon, _category):
            return FakeIndicator()


class FakeGLib:
    def idle_add(self, func, *args):
        func(*args)


def make_app(devices):
    return tray.TrayApp(FakeIndicatorModule(), FakeGtk(), FakeGLib(), devices)


def test_menu_lists_cast_and_audio_only_items_per_device():
    app = make_app([DEVICE])
    labels = [item.label for item in app.menu.get_children()]
    assert "Cast to woonkamer TV" in labels
    assert "  Audio only → woonkamer TV" in labels


def test_starting_a_session_swaps_menu_to_stop_and_disables_double_start(monkeypatch):
    started = []
    monkeypatch.setattr(
        tray.session,
        "ScreenSession",
        lambda device: types.SimpleNamespace(
            start=lambda: started.append(device), stop=lambda: None
        ),
    )
    app = make_app([DEVICE])
    cast_item = next(i for i in app.menu.get_children() if i.label == "Cast to woonkamer TV")
    cast_item.activate()
    assert started == [DEVICE]
    labels = [item.label for item in app.menu.get_children()]
    assert "Casting to woonkamer TV" in labels
    assert "Stop casting" in labels


def test_stopping_clears_session_and_rebuilds_menu(monkeypatch):
    stopped = []
    monkeypatch.setattr(
        tray.session,
        "ScreenSession",
        lambda device: types.SimpleNamespace(
            start=lambda: None, stop=lambda: stopped.append(device)
        ),
    )
    app = make_app([DEVICE])
    cast_item = next(i for i in app.menu.get_children() if i.label == "Cast to woonkamer TV")
    cast_item.activate()
    stop_item = next(i for i in app.menu.get_children() if i.label == "Stop casting")
    stop_item.activate()
    assert stopped == [DEVICE]
    labels = [item.label for item in app.menu.get_children()]
    assert "Cast to woonkamer TV" in labels
