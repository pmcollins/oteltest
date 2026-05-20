"""
Regression smoke test: requests HTTP client instrumentation.

This scenario exercises the popular requests instrumentation against a local
HTTP server so it does not depend on external network access.
"""

import json
import sys
import threading
from functools import cached_property
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from regression_tests.subjects import load_subject


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    import requests

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    try:
        url = f"http://127.0.0.1:{server.server_port}/users/42?active=true"
        response = requests.get(url, timeout=5)
        assert response.status_code == 200
        assert response.json()["path"] == "/users/42?active=true"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    print("requests workload complete")


class RequestsBasicRegressionOtelTest:
    @cached_property
    def subject(self):
        return load_subject()

    def requirements(self):
        return self.subject.requirements

    def environment_variables(self):
        return self.subject.environment_variables

    def wrapper_command(self):
        return self.subject.wrapper_command

    def on_start(self):
        return 10

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int):
        from oteltest.telemetry import get_spans, span_attribute_by_name

        assert (
            returncode == 0
        ), f"script failed with code {returncode}\nstderr:\n{stderr}"
        assert "requests workload complete" in stdout
        assert tel.trace_requests, "no trace requests received"

        spans = get_spans(tel)
        http_spans = [
            span
            for span in spans
            if span_attribute_by_name(span, "http.method") == "GET"
            or span_attribute_by_name(span, "http.request.method") == "GET"
        ]
        assert http_spans, "expected at least one requests HTTP span"

    def is_http(self):
        return True
