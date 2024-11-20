import abc
import time

from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from oteltest import Telemetry


class RequestHandler(abc.ABC):
    """
    The RequestHandler interface is meant to be implemented by users of the otelsink API. If you use the API,
    you'll want to create a RequestHandler implementation, instantiate it, and pass the instance to the GrpcSink
    constructor. As messages arrive, the callbacks defined by this interface will be invoked.

    grpc_sink = GrpcSink(MyRequestHandler())
    """

    @abc.abstractmethod
    def handle_logs(self, request: ExportLogsServiceRequest, headers):
        pass

    @abc.abstractmethod
    def handle_metrics(self, request: ExportMetricsServiceRequest, headers):
        pass

    @abc.abstractmethod
    def handle_trace(self, request: ExportTraceServiceRequest, headers):
        pass


class PrintHandler(RequestHandler):
    """
    A RequestHandler implementation that prints the received messages.
    """

    def handle_logs(self, request, headers):  # noqa: ARG002
        print_request(request)

    def handle_metrics(self, request, context):  # noqa: ARG002
        print_request(request)

    def handle_trace(self, request, context):  # noqa: ARG002
        print_request(request)


def print_request(request):
    print(str(MessageToDict(request)), flush=True)  # noqa: T201


class AccumulatingHandler(RequestHandler):
    def __init__(self):
        self.start_time = time.time_ns()
        self.telemetry = Telemetry()

    def handle_logs(self, request: ExportLogsServiceRequest, headers):  # noqa: ARG002
        self.telemetry.add_log(
            request,
            headers,
            self.get_test_elapsed_ms(),
        )

    def handle_metrics(
        self, request: ExportMetricsServiceRequest, headers
    ):  # noqa: ARG002
        self.telemetry.add_metric(
            request,
            headers,
            self.get_test_elapsed_ms(),
        )

    def handle_trace(self, request: ExportTraceServiceRequest, headers):  # noqa: ARG002
        self.telemetry.add_trace(
            request,
            headers,
            self.get_test_elapsed_ms(),
        )

    def get_test_elapsed_ms(self):
        return round((time.time_ns() - self.start_time) / 1e6)

    def telemetry_to_json(self):
        return self.telemetry.to_json()
