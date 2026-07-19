import urllib.error
import urllib.request

import pytest

from ubuntu_cast import stream


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
