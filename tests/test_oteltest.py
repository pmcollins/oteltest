import json
import os
import pickle
from typing import Mapping, Optional, Sequence

import pytest
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord
from opentelemetry.proto.metrics.v1.metrics_pb2 import Metric
from opentelemetry.proto.trace.v1.trace_pb2 import Span

from oteltest import OtelTest, telemetry, Telemetry
from oteltest.private import (
    get_next_json_file,
    is_test_class,
    load_oteltest_class_for_script,
    run_python_script,
    save_telemetry_json,
    Venv,
)
from oteltest.telemetry import (
    num_logs,
    stack_leaves,
    stack_logs,
    stack_metrics,
    stack_traces,
)


# fixtures


@pytest.fixture
def telemetry_fixture() -> Telemetry:
    return load_fixture("metrics_and_traces.pkl")


@pytest.fixture
def client_server_fixture() -> Telemetry:
    return load_fixture("client_server.pkl")


@pytest.fixture
def post_data_fixture():
    return load_fixture("post_data.pkl")


@pytest.fixture
def logs_fixture():
    return load_fixture("logs.pkl")


# tests


def test_get_next_json_file(tmp_path):
    module_name = "my_module_name"
    path_to_dir = str(tmp_path)

    next_file = get_next_json_file(path_to_dir, module_name)
    assert "my_module_name.0.json" == next_file

    save_telemetry_json(path_to_dir, next_file, "")

    next_file = get_next_json_file(path_to_dir, module_name)
    assert "my_module_name.1.json" == next_file

    save_telemetry_json(path_to_dir, next_file, "[1]")

    next_file = get_next_json_file(path_to_dir, module_name)
    assert "my_module_name.2.json" == next_file


def test_is_test_class():
    class K:
        pass

    class MyImpl(OtelTest):
        def environment_variables(self) -> Mapping[str, str]:
            pass

        def requirements(self) -> Sequence[str]:
            pass

        def wrapper_command(self) -> str:
            pass

        def on_start(self) -> Optional[float]:
            pass

        def on_stop(
            self, tel: Telemetry, stdout: str, stderr: str, returncode: int
        ) -> None:
            pass

        def is_http(self) -> bool:
            pass

    class MyOtelTest:
        pass

    assert not is_test_class(K)
    assert is_test_class(MyImpl)
    assert is_test_class(MyOtelTest)


def test_load_test_class_for_script():
    path = os.path.join(fixtures_dir, "script.py")
    klass = load_oteltest_class_for_script("script", path)
    assert klass is not None


def test_telemetry_functions(telemetry_fixture: Telemetry):
    assert len(telemetry_fixture.trace_requests)
    assert len(telemetry_fixture.trace_requests)
    assert telemetry.num_spans(telemetry_fixture) == 10
    assert telemetry.num_metrics(telemetry_fixture) == 21
    assert telemetry.metric_names(telemetry_fixture) == {
        "loop-counter",
        "process.runtime.cpython.context_switches",
        "process.runtime.cpython.cpu.utilization",
        "process.runtime.cpython.cpu_time",
        "process.runtime.cpython.gc_count",
        "process.runtime.cpython.memory",
        "process.runtime.cpython.thread_count",
        "system.cpu.time",
        "system.cpu.utilization",
        "system.disk.io",
        "system.disk.operations",
        "system.disk.time",
        "system.memory.usage",
        "system.memory.utilization",
        "system.network.dropped_packets",
        "system.network.errors",
        "system.network.io",
        "system.network.packets",
        "system.swap.usage",
        "system.swap.utilization",
        "system.thread_count",
    }
    span = telemetry.first_span(telemetry_fixture)
    assert span.trace_id.hex() == "0adffbc2cb9f3cdb09f6801a788da973"


def test_span_attribute_by_name(client_server_fixture: Telemetry):
    span = telemetry.first_span(client_server_fixture)
    assert telemetry.span_attribute_by_name(span, "http.method") == "GET"


def test_run_python_script():
    env = {"aaa": "bbb"}

    class Tester:

        def __init__(self):
            self.python_script_cmd = None
            self.env = None

        def start_subprocess(self, python_script_cmd, env):
            self.python_script_cmd = python_script_cmd
            self.env = env
            return FakeSubProcess()

    t = Tester()
    run_python_script(
        t.start_subprocess,
        "script_dir",
        "script",
        FakeOtelTest(env=env),
        Venv("venv_dir"),
    )
    assert t.python_script_cmd == [
        "venv_dir/bin/python",
        "script_dir/script",
    ]
    assert t.env == env


def test_stack_traces(telemetry_fixture):
    spans = stack_traces(telemetry_fixture)
    assert len(spans) == 10
    for span in spans:
        assert type(span) is Span


def test_stack_metrics(telemetry_fixture):
    metrics = stack_metrics(telemetry_fixture)
    assert len(metrics) == 21
    for metric in metrics:
        assert type(metric) is Metric


def test_stack_logs(logs_fixture):
    logs = stack_logs(logs_fixture)
    assert len(logs) == 16
    for log in logs:
        assert type(log) is LogRecord


def test_get_logs(logs_fixture):
    assert num_logs(logs_fixture) == 16


# utils


fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(fname):
    with open(get_path_to_fixture(fname), "rb") as file:
        return pickle.load(file)


def get_path_to_fixture(fname):
    return os.path.join(fixtures_dir, fname)


def telemetry_from_json(json_str: str) -> telemetry.Telemetry:
    return telemetry_from_dict(json.loads(json_str))


def telemetry_from_dict(d) -> telemetry.Telemetry:
    return telemetry.Telemetry(
        log_requests=d["log_requests"],
        metric_requests=d["metric_requests"],
        trace_requests=d["trace_requests"],
    )


class FakeOtelTest:

    def __init__(self, env=None, reqs=None, wrapper=None):
        self.env = env or {}
        self.reqs = reqs or []
        self.wrapper = wrapper or ""

    def environment_variables(self) -> Mapping[str, str]:
        return self.env

    def requirements(self) -> Sequence[str]:
        return self.reqs

    def wrapper_command(self) -> str:
        return self.wrapper

    def on_start(self) -> Optional[float]:
        pass

    def on_stop(
        self, tel: Telemetry, stdout: str, stderr: str, returncode: int
    ) -> None:
        pass


class FakeSubProcess:

    returncode = 0

    def communicate(self, timeout):
        stdout = ""
        stderr = ""
        return stdout, stderr

    def kill(self):
        pass
