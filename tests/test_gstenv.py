from ubuntu_cast.gstenv import sanitized_env


def test_snap_components_are_stripped_from_path_lists(monkeypatch):
    monkeypatch.setenv(
        "GST_PLUGIN_PATH", "/snap/alacritty/160/usr/lib/gstreamer-1.0:/usr/local/lib/gstreamer-1.0"
    )
    assert sanitized_env()["GST_PLUGIN_PATH"] == "/usr/local/lib/gstreamer-1.0"


def test_path_list_var_dropped_when_only_snap_remains(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/snap/alacritty/160/usr/lib/x86_64-linux-gnu/dri")
    assert "LD_LIBRARY_PATH" not in sanitized_env()


def test_snap_scanner_is_dropped(monkeypatch):
    monkeypatch.setenv("GST_PLUGIN_SCANNER", "/snap/alacritty/160/usr/lib/gst-plugin-scanner")
    assert "GST_PLUGIN_SCANNER" not in sanitized_env()


def test_user_snap_cache_dir_is_dropped(monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", "/home/jerry/snap/alacritty/common/.cache")
    assert "XDG_CACHE_HOME" not in sanitized_env()


def test_non_snap_values_pass_through(monkeypatch):
    monkeypatch.setenv("GST_PLUGIN_SCANNER", "/usr/libexec/gstreamer-1.0/gst-plugin-scanner")
    monkeypatch.setenv("XDG_CACHE_HOME", "/home/jerry/.cache")
    env = sanitized_env()
    assert env["GST_PLUGIN_SCANNER"] == "/usr/libexec/gstreamer-1.0/gst-plugin-scanner"
    assert env["XDG_CACHE_HOME"] == "/home/jerry/.cache"
