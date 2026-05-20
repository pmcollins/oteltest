"""
Regression smoke test: Flask server instrumentation.

This scenario exercises Flask instrumentation against a local Werkzeug server,
avoiding external network dependencies.
"""

import sys
import threading
from functools import cached_property
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from regression_tests.subjects import load_subject


def create_app():
    from flask import Flask, jsonify

    app = Flask(__name__)

    @app.get("/hello/<name>")
    def hello(name):
        return jsonify({"hello": name})

    return app


if __name__ == "__main__":
    import requests
    from werkzeug.serving import make_server

    app = create_app()
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    try:
        url = f"http://127.0.0.1:{server.server_port}/hello/alice?debug=true"
        response = requests.get(url, timeout=5)
        assert response.status_code == 200
        assert response.json() == {"hello": "alice"}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    print("flask workload complete")


class FlaskBasicRegressionOtelTest:
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
        assert "flask workload complete" in stdout
        assert tel.trace_requests, "no trace requests received"

        spans = get_spans(tel)
        flask_spans = [
            span
            for span in spans
            if span_attribute_by_name(span, "http.route") == "/hello/<name>"
            or span_attribute_by_name(span, "url.path") == "/hello/alice"
        ]
        assert flask_spans, "expected at least one Flask server span"

    def is_http(self):
        return True
