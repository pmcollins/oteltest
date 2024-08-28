from lib import trace_loop

SERVICE_NAME = "my-otel-test"
NUM_ADDS = 12

if __name__ == "__main__":
    trace_loop(NUM_ADDS)

# Since we're not inheriting from the OtelTest base class (to avoid depending on it) we make sure our class name
# contains "OtelTest".
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
