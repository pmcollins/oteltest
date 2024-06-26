import dataclasses
import json
from typing import List, Optional, Union

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


@dataclasses.dataclass
class Request:
    """
    Wraps a grpc message (metric, trace, or log), http headers that came in with the message, and the time elapsed
    between the start of the test and the receipt of the message.
    """

    pbreq: Union[
        ExportTraceServiceRequest, ExportMetricsServiceRequest, ExportLogsServiceRequest
    ]
    headers: dict
    test_elapsed_ms: int

    def get_header(self, name):
        return self.headers.get(name)

    def to_json(self):
        return json.dumps(self.to_dict())

    def to_dict(self):
        return {
            "pbreq": MessageToDict(self.pbreq),
            "headers": self.headers,
            "test_elapsed_ms": self.test_elapsed_ms,
        }


class Telemetry:
    """
    Wraps lists of metric, trace, and log requests sent during a single oteltest script run. An instance is passed in to
    OtelTest#on_stop().
    """

    def __init__(
      self,
      metric_requests: Optional[List[Request]] = None,
      trace_requests: Optional[List[Request]] = None,
      log_requests: Optional[List[Request]] = None,
    ):
        self.metric_requests: List[Request] = metric_requests or []
        self.trace_requests: List[Request] = trace_requests or []
        self.log_requests: List[Request] = log_requests or []

    def add_metric(
      self, pbreq: ExportMetricsServiceRequest, headers: dict, test_elapsed_ms: int
    ):
        self.metric_requests.append(Request(pbreq, headers, test_elapsed_ms))

    def add_trace(
      self, pbreq: ExportTraceServiceRequest, headers: dict, test_elapsed_ms: int
    ):
        self.trace_requests.append(Request(pbreq, headers, test_elapsed_ms))

    def add_log(
      self, pbreq: ExportLogsServiceRequest, headers: dict, test_elapsed_ms: int
    ):
        self.log_requests.append(Request(pbreq, headers, test_elapsed_ms))

    def get_metric_requests(self) -> List[Request]:
        return self.metric_requests

    def get_trace_requests(self) -> List[Request]:
        return self.trace_requests

    def get_logs_requests(self) -> List[Request]:
        return self.log_requests

    def __str__(self):
        return self.to_json()

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)

    def to_dict(self):
        return {
            "metric_requests": [req.to_dict() for req in self.metric_requests],
            "trace_requests": [req.to_dict() for req in self.trace_requests],
            "log_requests": [req.to_dict() for req in self.log_requests],
        }


_metrics_path = ["metric_requests", "resource_metrics", "scope_metrics", "metrics"]
_trace_path = ["trace_requests", "resource_spans", "scope_spans", "spans"]


def num_metrics(telemetry) -> int:
    return len(stack_leaves(telemetry, *_metrics_path))


def metric_names(telemetry) -> set:
    return {
        leaf.name for leaf in
        stack_leaves(telemetry, *_metrics_path)
    }


def num_spans(telemetry) -> int:
    return len(stack_leaves(telemetry, *_trace_path))


def span_names(telemetry) -> set:
    return {
        leaf.name for leaf in
        stack_leaves(telemetry, *_trace_path)
    }


def stack_leaves(telemetry, k1, k2, k3, k4):
    out = []
    for a1 in getattr(telemetry, k1):
        for a2 in getattr(a1.pbreq, k2):
            for a3 in getattr(a2, k3):
                for a4 in getattr(a3, k4):
                    out.append(a4)
    return out


def has_trace_header(telemetry, key, expected) -> bool:
    for req in telemetry.trace_requests:
        actual = req.get_header(key)
        if expected == actual:
            return True
    return False


def first_span(tel: Telemetry):
    return span_at_index(tel, 0, 0, 0, 0)


def span_at_index(tel: Telemetry, i: int, j: int, k: int, l: int):
    if len(tel.trace_requests):
        req = tel.trace_requests[i]
        if len(req.pbreq.resource_spans):
            rs = req.pbreq.resource_spans[j]
            if len(rs.scope_spans):
                ss = rs.scope_spans[k]
                if len(ss.spans):
                    return ss.spans[l]
    return None


def span_attribute_by_name(span, attr_name) -> Optional[str]:
    for attr in span.attributes:
        if attr.key == attr_name:
            if attr.value.HasField("string_value"):
                return attr.value.string_value
    return None
