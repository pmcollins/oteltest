from lib import trace_loop

SERVICE_NAME = "my-otel-test"
NUM_ADDS = 12


if __name__ == "__main__":
    trace_loop(NUM_ADDS)


# Since we're not inheriting from the OtelTest base class (to avoid depending on it) we make sure our class name
# contains "OtelTest".
class MyOtelTest:
    def requirements(self):
        return (
            "opentelemetry-distro",
            "opentelemetry-instrumentation-system-metrics",
            "opentelemetry-exporter-otlp-proto-grpc",
        )

    def environment_variables(self):
        return {
            "OTEL_SERVICE_NAME": SERVICE_NAME,
        }

    def wrapper_command(self):
        return "opentelemetry-instrument"

    def on_start(self):
        pass

    def on_stop(self, telemetry, stdout: str, stderr: str, returncode: int) -> None:
        pass

    def is_http(self):
        return False
