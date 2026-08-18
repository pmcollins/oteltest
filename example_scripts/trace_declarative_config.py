from opentelemetry import trace

SERVICE_NAME = "oteltest-declarative-config"
SPAN_NAME = "declaratively-configured-span"


if __name__ == "__main__":
    tracer = trace.get_tracer("oteltest-declarative-config")
    with tracer.start_as_current_span(SPAN_NAME):
        print("created span with declarative configuration")


class DeclarativeConfigOtelTest:
    def requirements(self):
        return (
            "opentelemetry-distro==0.65b0",
            "opentelemetry-sdk[file-configuration]==1.44.0",
            "opentelemetry-exporter-otlp-proto-grpc==1.44.0",
        )

    def declarative_configuration(self):
        return f"""
        file_format: "1.0"

        resource:
          attributes:
            - name: service.name
              value: {SERVICE_NAME}

        tracer_provider:
          processors:
            - simple:
                exporter:
                  otlp_grpc:
                    endpoint: http://localhost:4317
        """

    def wrapper_command(self):
        return "opentelemetry-instrument"

    def on_start(self):
        return None

    def on_stop(self, telemetry, stdout, stderr, returncode):
        from oteltest.telemetry import get_attribute, get_spans

        spans = get_spans(telemetry)
        assert returncode == 0, stderr
        assert len(spans) == 1
        assert spans[0].name == SPAN_NAME

        trace_request = telemetry.get_trace_requests()[0]
        resource = trace_request.pbreq.resource_spans[0].resource
        service_name = get_attribute(resource.attributes, "service.name")
        assert service_name is not None
        assert service_name.value.string_value == SERVICE_NAME

    def is_http(self):
        return False
