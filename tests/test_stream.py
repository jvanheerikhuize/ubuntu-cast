import contextlib
import os
import urllib.error
import urllib.request

import pytest

from ubuntu_cast import stream


@contextlib.contextmanager
def running_server(**kwargs):
    running = stream.start(**kwargs)
    try:
        yield running
    finally:
        running.shutdown()
        running.server_close()


@pytest.fixture
def server():
    running = stream.start(["printf", "mp3-bytes"])
    yield running
    running.shutdown()
    running.server_close()


def test_stream_serves_pipeline_stdout(server):
    url = f"http://127.0.0.1:{server.server_port}{stream.STREAM_PATH}"
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        assert response.headers["Content-Type"] == "audio/mpeg"
        assert response.read() == b"mp3-bytes"


def test_content_type_is_configurable():
    running = stream.start(["printf", "mp4-bytes"], content_type="video/mp4")
    try:
        url = f"http://127.0.0.1:{running.server_port}{stream.STREAM_PATH}"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.headers["Content-Type"] == "video/mp4"
            assert response.read() == b"mp4-bytes"
    finally:
        running.shutdown()
        running.server_close()


def test_unknown_path_is_404(server):
    url = f"http://127.0.0.1:{server.server_port}/nope"
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(url, timeout=5)
    assert excinfo.value.code == 404


def test_factory_builds_a_fresh_command_per_connection():
    calls = []

    def factory():
        calls.append(len(calls))
        return ["printf", f"take-{len(calls)}"], ()

    with running_server(command_factory=factory) as running:
        url = f"http://127.0.0.1:{running.server_port}{stream.STREAM_PATH}"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.read() == b"take-1"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.read() == b"take-2"
    assert calls == [0, 1]


def test_factory_fds_are_closed_in_the_parent_after_spawn():
    read_end, write_end = os.pipe()
    os.write(write_end, b"fd-bytes")
    os.close(write_end)

    def factory():
        return ["cat", f"/proc/self/fd/{read_end}"], (read_end,)

    with running_server(command_factory=factory) as running:
        url = f"http://127.0.0.1:{running.server_port}{stream.STREAM_PATH}"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.read() == b"fd-bytes"
    # The handler must have closed its copy of the factory's fd.
    with pytest.raises(OSError):
        os.fstat(read_end)


def test_factory_failure_returns_503():
    def factory():
        raise RuntimeError("portal went away")

    with running_server(command_factory=factory) as running:
        url = f"http://127.0.0.1:{running.server_port}{stream.STREAM_PATH}"
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(url, timeout=5)
        assert excinfo.value.code == 503


def test_command_and_factory_are_mutually_exclusive():
    with pytest.raises(ValueError):
        stream.StreamServer(["printf", "x"], command_factory=lambda: ([], ()))
    with pytest.raises(ValueError):
        stream.StreamServer()
