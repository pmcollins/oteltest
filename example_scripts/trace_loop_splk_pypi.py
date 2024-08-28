from lib import trace_loop

SERVICE_NAME = "my-otel-test"
NUM_ADDS = 12

if __name__ == "__main__":
    trace_loop(NUM_ADDS)

class MyOtelTest:
    def requirements(self):
        return ("splunk-opentelemetry[otlp]",)

    def environment_variables(self):
        return {
            "OTEL_SERVICE_NAME": SERVICE_NAME,
        }

    def wrapper_command(self):
        return "opentelemetry-instrument"

    def on_start(self):
        return None

    def on_stop(self, telemetry, stdout: str, stderr: str, returncode: int) -> None:
        print(f"script completed with return code {returncode}")

    def is_http(self):
        return False
