"""
Baseline test: Basic trace export via HTTP with protobuf encoding

This test establishes the baseline behavior for the most common use case:
exporting traces over HTTP using protobuf encoding.

Expected behavior:
- Script completes successfully (returncode 0)
- Telemetry is received by OTLP receiver
- Span structure matches OTLP specification
- Attributes and events are preserved
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

SERVICE_NAME = "baseline-trace-http-protobuf"

if __name__ == "__main__":
    # Set up tracing
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Create test span
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("test-span") as span:
        span.set_attribute("test.key", "test.value")
        span.set_attribute("test.number", 42)
        span.add_event("test-event", {"event.key": "event.value"})

    # Ensure export
    provider.force_flush()
    provider.shutdown()

    print("✓ Test complete")


class BaselineTraceHttpProtobufOtelTest:
    """oteltest test class"""

    def requirements(self):
        return [
            "opentelemetry-api==1.27.0",
            "opentelemetry-sdk==1.27.0",
            "opentelemetry-exporter-otlp-proto-http==1.27.0",
        ]

    def environment_variables(self):
        return {"OTEL_SERVICE_NAME": SERVICE_NAME}

    def wrapper_command(self):
        return None  # Direct SDK usage

    def on_start(self):
        return 10  # Wait up to 10 seconds

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int):
        """Validate baseline behavior"""
        from oteltest.telemetry import count_spans, first_span

        # Basic success checks
        assert returncode == 0, f"Script failed with code {returncode}"
        assert "✓" in stdout, "Script didn't complete successfully"
        assert len(tel.trace_requests) > 0, "No trace requests received"

        # Validate span count
        num_spans = count_spans(tel)
        assert num_spans == 1, f"Expected 1 span, got {num_spans}"

        # Get the span using helper function
        span = first_span(tel)
        assert span is not None, "No span found"
        assert span.name == "test-span", f"Wrong span name: {span.name}"

        # Attributes
        attrs = {attr.key: attr.value for attr in span.attributes}
        assert "test.key" in attrs, "Missing test.key attribute"
        assert attrs["test.key"].string_value == "test.value"
        assert "test.number" in attrs, "Missing test.number attribute"
        assert attrs["test.number"].int_value == 42

        # Events
        assert len(span.events) == 1, f"Expected 1 event, got {len(span.events)}"
        event = span.events[0]
        assert event.name == "test-event", f"Wrong event name: {event.name}"

        event_attrs = {attr.key: attr.value for attr in event.attributes}
        assert "event.key" in event_attrs
        assert event_attrs["event.key"].string_value == "event.value"

        print("✓ All baseline assertions passed")

    def is_http(self):
        return True  # Use HTTP receiver (port 4318)
