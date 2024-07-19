import json
import os
import pickle
from typing import Mapping, Optional, Sequence

import pytest

from oteltest import OtelTest, telemetry, Telemetry
from oteltest.private import (
    get_next_json_file,
    is_test_class,
    load_test_class_for_script,
    run_python_script,
    save_telemetry_json,
    Venv,
)


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

    class MyOtelTest:
        pass

    assert not is_test_class(K)
    assert is_test_class(MyImpl)
    assert is_test_class(MyOtelTest)


def test_load_test_class_for_script():
    path = os.path.join(fixtures_dir, "script.py")
    klass = load_test_class_for_script("script", path)
    assert klass is not None


def test_telemetry_functions(metrics_trace_fixture: Telemetry):
    assert len(metrics_trace_fixture.trace_requests)
    assert len(metrics_trace_fixture.trace_requests)
    assert telemetry.num_spans(metrics_trace_fixture) == 10
    assert telemetry.num_metrics(metrics_trace_fixture) == 21
    assert telemetry.metric_names(metrics_trace_fixture) == {
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
    span = telemetry.first_span(metrics_trace_fixture)
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


class FakeSubProcess:

    returncode = 0

    def communicate(self, timeout):
        stdout = ""
        stderr = ""
        return stdout, stderr

    def kill(self):
        pass


# fixtures


@pytest.fixture
def metrics_trace_fixture() -> Telemetry:
    return load_fixture("metrics_trace.pkl")


@pytest.fixture
def client_server_fixture() -> Telemetry:
    return load_fixture("client_server.pkl")


# utils


def telemetry_from_json(json_str: str) -> telemetry.Telemetry:
    return telemetry_from_dict(json.loads(json_str))


def telemetry_from_dict(d) -> telemetry.Telemetry:
    return telemetry.Telemetry(
        log_requests=d["log_requests"],
        metric_requests=d["metric_requests"],
        trace_requests=d["trace_requests"],
    )


fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(fname):
    with open(get_path_to_fixture(fname), "rb") as file:
        return pickle.load(file)


def get_path_to_fixture(fname):
    return os.path.join(fixtures_dir, fname)


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
