from __future__ import annotations

from opentelemetry import trace

SERVICE_NAME = "my-otel-test"

if __name__ == "__main__":
    tracer = trace.get_tracer("my-tracer")
    with tracer.start_as_current_span("aaa"), tracer.start_as_current_span("bbb"), tracer.start_as_current_span("ccc"):
        print("hola mundo")


class MyOtelTest:
    def requirements(self):
        return "opentelemetry-distro", "opentelemetry-exporter-otlp-proto-http"

    def environment_variables(self):
        return {
            "OTEL_SERVICE_NAME": SERVICE_NAME,
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        }

    def wrapper_command(self):
        return "opentelemetry-instrument"

    def on_start(self):
        return None

    def on_stop(self, telemetry, stdout: str, stderr: str, returncode: int) -> None:
        pass

    def is_http(self):
        return True
