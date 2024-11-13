import logging
import socket
import threading
from concurrent import futures
from http.server import BaseHTTPRequestHandler, HTTPServer

import grpc  # type: ignore
from opentelemetry.proto.collector.logs.v1 import (  # type: ignore
    logs_service_pb2_grpc,
)
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,  # type: ignore
)
from opentelemetry.proto.collector.metrics.v1 import (  # type: ignore
    metrics_service_pb2_grpc,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,  # type: ignore
)
from opentelemetry.proto.collector.trace.v1 import (  # type: ignore
    trace_service_pb2_grpc,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,  # type: ignore
)

from oteltest.sink.handler import PrintHandler, RequestHandler
from oteltest.sink.private import (
    _LogsServiceServicer,
    _MetricsServiceServicer,
    _TraceServiceServicer,
)


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.bind(("127.0.0.1", port))
            return False
        except socket.error:
            return True


def raise_if_port_in_use(port):
    if is_port_in_use(port):
        raise Exception(f"port {port} is in use")


class GrpcSink:
    """
    This is an OTel GRPC server to which you can send metrics, traces, and
    logs. It requires a RequestHandler implementation passed in.
    """

    def __init__(
        self,
        request_handler: RequestHandler,
        logger: logging.Logger,
        max_workers: int = 10,
        port: int = 4317,
    ):
        self.svr = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        trace_service_pb2_grpc.add_TraceServiceServicer_to_server(
            _TraceServiceServicer(request_handler.handle_trace), self.svr
        )
        metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server(
            _MetricsServiceServicer(request_handler.handle_metrics), self.svr
        )
        logs_service_pb2_grpc.add_LogsServiceServicer_to_server(
            _LogsServiceServicer(request_handler.handle_logs), self.svr
        )
        self.logger = logger
        self.port = port
        address = f"0.0.0.0:{port}"
        self.svr.add_insecure_port(address)
        logger.info(f"grpc sink at address {address} ready to start")

    def start(self):
        """Starts the server. Does not block."""
        self.svr.start()

    def wait_for_termination(self):
        """Blocks until the server stops."""
        try:
            self.svr.wait_for_termination()
        except BaseException:
            self.logger.info("terminated")

    def stop(self):
        """Stops the server immediately."""
        self.svr.stop(grace=None)


class HttpSink:

    def __init__(self, listener, logger: logging.Logger, port=4318, daemon=True):
        self.listener = listener
        self.logger = logger
        self.port = port
        self.handlers = {
            "/v1/traces": self.handle_trace,
            "/v1/metrics": self.handle_metrics,
            "/v1/logs": self.handle_logs,
        }
        self.svr_thread = threading.Thread(target=self.run_server)
        self.svr_thread.daemon = daemon
        self.logger.info(f"Set up http sink on port {port}")

    def start(self):
        self.svr_thread.start()

    def run_server(self):
        class Handler(BaseHTTPRequestHandler):

            # noinspection PyPep8Naming
            def do_POST(this):
                # /v1/traces
                content_length = int(this.headers["Content-Length"])
                post_data = this.rfile.read(content_length)

                otlp_handler_func = self.handlers.get(this.path)
                if otlp_handler_func:
                    # noinspection PyArgumentList
                    otlp_handler_func(
                        post_data, {k: v for k, v in this.headers.items()}
                    )

                this.send_response(200)
                this.send_header("Content-type", "text/html")
                this.end_headers()

                this.wfile.write("OK".encode("utf-8"))

        # noinspection PyTypeChecker
        httpd = HTTPServer(("", self.port), Handler)
        httpd.serve_forever()

    def handle_trace(self, post_data, headers):
        req = ExportTraceServiceRequest()
        req.ParseFromString(post_data)
        self.listener.handle_trace(req, headers)

    def handle_metrics(self, post_data, headers):
        req = ExportMetricsServiceRequest()
        req.ParseFromString(post_data)
        self.listener.handle_metrics(req, headers)

    def handle_logs(self, post_data, headers):
        req = ExportLogsServiceRequest()
        req.ParseFromString(post_data)
        self.listener.handle_logs(req, headers)

    def stop(self):
        self.svr_thread.join()


def run_grpc(logger):
    logger.info("Starting grpc server")

    raise_if_port_in_use(4317)
    sink = GrpcSink(PrintHandler(), logger)
    sink.start()
    sink.wait_for_termination()


def run_http(logger):
    logger.info("Starting http server")

    raise_if_port_in_use(4318)
    sink = HttpSink(PrintHandler(), daemon=False)
    sink.start()
