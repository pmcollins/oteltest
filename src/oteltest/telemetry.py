import dataclasses
import json
from collections.abc import Iterable
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


_metrics_path = [
    "metric_requests",
    "pbreq",
    "resource_metrics",
    "scope_metrics",
    "metrics",
]
_span_path = ["trace_requests", "pbreq", "resource_spans", "scope_spans", "spans"]
_logs_path = ["log_requests", "pbreq", "resource_logs", "scope_logs", "log_records"]


def has_log_attribute(tel, key) -> bool:
    for log in get_logs(tel):
        for attribute in log.attributes:
            if attribute.key == key:
                return True
    return False


def get_attribute(attributes, key):
    for attribute in attributes:
        if attribute.key == key:
            return attribute
    return None


def count_metrics(telemetry) -> int:
    return len(get_metrics(telemetry))


def get_metric_names(telemetry) -> set:
    return {leaf.name for leaf in get_metrics(telemetry)}


def count_spans(telemetry) -> int:
    return len(get_spans(telemetry))


def count_logs(telemetry) -> int:
    return len(get_logs(telemetry))


def get_span_names(telemetry) -> set:
    return {leaf.name for leaf in get_spans(telemetry)}


def get_metrics(telemetry):
    return extract_leaves(telemetry, *_metrics_path)


def get_spans(telemetry):
    return extract_leaves(telemetry, *_span_path)


def get_logs(telemetry):
    return extract_leaves(telemetry, *_logs_path)


def extract_leaves(items, key, *remaining_keys):
    out = []
    for item in items if isinstance(items, Iterable) else [items]:
        next_items = getattr(item, key)
        if remaining_keys:
            out.extend(extract_leaves(next_items, *remaining_keys))
        else:
            if isinstance(next_items, Iterable):
                out.extend(next_items)
            else:
                out.append(next_items)
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
