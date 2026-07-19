from ubuntu_cast import portal


def test_request_path_encodes_unique_name():
    assert portal.request_path(":1.42", "tok") == "/org/freedesktop/portal/desktop/request/1_42/tok"


def test_request_path_replaces_every_dot():
    assert portal.request_path(":1.2.3", "t").endswith("/1_2_3/t")


def test_select_sources_asks_the_portal_to_persist_the_selection():
    options = portal.select_sources_options(None)
    assert options["persist_mode"] == ("u", portal.PERSIST_UNTIL_REVOKED)
    assert "restore_token" not in options


def test_select_sources_passes_a_saved_token_to_skip_the_dialog():
    options = portal.select_sources_options("tok-123")
    assert options["restore_token"] == ("s", "tok-123")
