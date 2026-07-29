import logging
import time
from unittest import mock

from oteltest.sink import HttpSink


def wait_for_http_server(sink):
    deadline = time.monotonic() + 2
    while sink.httpd is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert sink.httpd is not None


def test_http_sink_releases_port_when_stopped():
    logger = logging.getLogger("test-http-sink")
    first_sink = HttpSink(mock.Mock(), logger, port=0)
    first_sink.start()
    wait_for_http_server(first_sink)
    port = first_sink.httpd.server_port
    first_sink.stop()

    second_sink = HttpSink(mock.Mock(), logger, port=port)
    second_sink.start()
    try:
        wait_for_http_server(second_sink)
    finally:
        second_sink.stop()
