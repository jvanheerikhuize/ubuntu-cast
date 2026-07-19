from ubuntu_cast import portal


def test_request_path_encodes_unique_name():
    assert portal.request_path(":1.42", "tok") == "/org/freedesktop/portal/desktop/request/1_42/tok"


def test_request_path_replaces_every_dot():
    assert portal.request_path(":1.2.3", "t").endswith("/1_2_3/t")
