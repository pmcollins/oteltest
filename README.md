# oteltest

[![PyPI - Version](https://img.shields.io/pypi/v/oteltest.svg)](https://pypi.org/project/oteltest)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/oteltest.svg)](https://pypi.org/project/oteltest)

-----

**Table of Contents**

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install oteltest
```

## Overview

The `oteltest` package contains utilities for testing OpenTelemetry Python scenarios.

### oteltest

The `oteltest` command runs black box tests against Python scripts that send telemetry.

#### Execution

With the virtual environment (into which you've installed `oteltest`) active, run `oteltest` as a shell command and
provide a directory as an argument:

```shell
oteltest my_script_dir
```

This will attempt to run all [oteltest-eligible](#script-eligibility) scripts in `my_script_dir`, non-recursively.

#### Operation

Running `oteltest` against a directory containing only `my_script.py`

1) Starts an OTLP or HTTP listener ([otelsink](#otelsink))
2) Creates a new Python virtual environment with `requirements()`
3) In that environment, starts running `my_script.py` in a subprocess
4) Calls `on_start()`
5) Depending on the return value from `on_start()`, waits for `my_script.py` to complete
6) Stops otelsink
7) Calls `on_stop()` with otelsink's received telemetry and script output
8) Writes the telemetry to a `.json` file next to the script (script name but with ".{number}.json" instead of ".py")

#### Script Eligibility

For a Python script to be runnable by `oteltest`, it must implement the [OtelTest](src/oteltest/__init__.py)
abstract base class, either formally by inheriting from `OtelTest`, or informally by merely containing the name
"OtelTest" and implementing the methods. The script below has an implementation called `MyOtelTest`:

```python
import time

from opentelemetry import trace

SERVICE_NAME = "my-otel-test"
NUM_ADDS = 12

if __name__ == "__main__":
    tracer = trace.get_tracer("my-tracer")
    for i in range(NUM_ADDS):
        with tracer.start_as_current_span("my-span"):
            print(f"simple_loop.py: {i+1}/{NUM_ADDS}")
            time.sleep(0.5)


# The class name must contain 'OtelTest' to be recognized by the test runner if not inheriting from the base class
class MyOtelTest:
    def requirements(self):
        """
        Return a sequence of requirements formatted for pip install.
        """
        return ["opentelemetry-distro", "opentelemetry-exporter-otlp-proto-grpc"]

    def environment_variables(self):
        return {"OTEL_SERVICE_NAME": SERVICE_NAME}

    def wrapper_command(self):
        return "opentelemetry-instrument"

    def on_start(self):
        """
        Return None to let the script run indefinitely, or a float indicating seconds to wait before terminating.
        """
        return None

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int) -> None:
        print(f"script completed with return code {returncode}")

    def is_http(self) -> bool:
        """
        Return True to use HTTP for telemetry collection (port 4318), False to use gRPC (port 4317).
        Defaults to False (gRPC).
        """
        return False
```

Here's a client-server example:

```python
import time
from typing import Mapping, Optional, Sequence


PORT = 8002
HOST = "127.0.0.1"


if __name__ == "__main__":
    from flask import Flask

    app = Flask(__name__)

    @app.route("/")
    def home():
        return "hello"

    app.run(port=PORT, host=HOST)


# The class name must contain 'OtelTest' to be recognized by the test runner if not inheriting from the base class
class FlaskOtelTest:
    def environment_variables(self) -> Mapping[str, str]:
        return {}

    def requirements(self) -> Sequence[str]:
        return (
            "flask",
            "opentelemetry-distro",
            "opentelemetry-exporter-otlp-proto-grpc",
            "opentelemetry-instrumentation-flask",
        )

    def wrapper_command(self) -> str:
        return "opentelemetry-instrument"

    def on_start(self) -> Optional[float]:
        import http.client

        # Todo: replace this sleep with a liveness check!
        time.sleep(10)

        conn = http.client.HTTPConnection(HOST, PORT)
        conn.request("GET", "/")
        print("response:", conn.getresponse().read().decode())
        conn.close()

        # The return value of on_script_start() tells oteltest the number of seconds to wait for the script to complete.
        # In this case, we indicate 30 (seconds), which, once elapsed, will cause the script to be terminated, if it's
        # still running. If we return `None` then the script will run indefinitely.
        return 30

    def on_stop(self, telemetry, stdout: str, stderr: str, returncode: int) -> None:
        # you can do something with the telemetry here, e.g. make assertions etc.
        print("done")

    def is_http(self) -> bool:
        return False
```

#### Declarative configuration

Define `declarative_configuration()` to keep an OpenTelemetry declarative
configuration YAML document in the test script. Oteltest writes the document to
a temporary `.yaml` file, sets `OTEL_CONFIG_FILE` for the script process, and
removes the file after the process stops.

```python
class DeclarativeConfigOtelTest:
    # Implement the other OtelTest methods as usual.

    def declarative_configuration(self):
        return """
        file_format: "1.0"

        resource:
          attributes:
            - name: service.name
              value: declarative-test

        tracer_provider:
          processors:
            - batch:
                exporter:
                  otlp_grpc:
                    endpoint: http://localhost:4317
        """
```

Oteltest removes the common indentation before it writes the document. It
otherwise preserves the content, including environment variable substitutions
such as `${OTEL_SERVICE_NAME}`. The OpenTelemetry SDK installed by
`requirements()` parses and validates the document.

The method is optional. Tests that configure OpenTelemetry through environment
variables do not need to define it. The `environment_variables()` method is
optional too; omit it if the child process needs no variables. You can use it
with declarative configuration to supply application settings and values for
`${ENV_VAR}` references in the YAML. Do not use it to set `OTEL_CONFIG_FILE` or
the deprecated `OTEL_EXPERIMENTAL_CONFIG_FILE`; Oteltest manages the
configuration file path. See
[`trace_declarative_config.py`](example_scripts/trace_declarative_config.py) for
a complete runnable example.

#### OpAMP remote configuration

Define `on_opamp()` on an oteltest class to start an OpAMP HTTP server at
`http://127.0.0.1:4320/v1/opamp` for that test. The method receives the agent's
effective configuration, remote configuration status, and remote configuration
error. The status is `None`, `"applying"`, `"applied"`, or `"failed"`. On the
first request, these values are `None` when the agent has not reported them.
Later calls receive the latest values known by the server, even when the agent
omits an unchanged value from its request.

Return a dictionary to send it to the agent as remote configuration. Return
`None` to send no new configuration.

```python
class MyOtelTest(OtelTest):
    # Implement the other OtelTest methods as usual.

    def on_opamp(
        self,
        effective_config,
        remote_config_status,
        remote_config_error,
    ):
        if effective_config is None:
            return {"file_format": "1.0-rc.1"}

        assert remote_config_status == "applied", remote_config_error
        assert effective_config["file_format"] == "1.0-rc.1"
        return None
```

The same method works on a name-only class that does not inherit from
`OtelTest`. When the class does not define or override `on_opamp()`,
oteltest does not start an OpAMP server. This initial implementation supports
one JSON or `text/plain; format=properties` configuration document. Oteltest
decodes either format into the `effective_config` dictionary.

### otelsink

`otelsink` is a gRPC (or HTTP) server that listens for OTel metrics, traces, and logs.

#### Operation

You can run otelsink either from the command line by using the `otelsink` command (installed when you
`pip install oteltest`), or programmatically.

Either way, `otelsink` runs a gRPC server listening on 0.0.0.0:4317 by default. To run an HTTP server listening on 4318,
use the `--http` flag.

#### Command Line

```
% otelsink
starting otelsink
- Set up grpc sink at address 0.0.0.0:4317
```

```
% otelsink --http
- Set up http sink on port 4318
```


#### Programmatic

```python
from oteltest.sink import GrpcSink, RequestHandler

class MyHandler(RequestHandler):
    def handle_logs(self, request, headers):
        print(f"received log request: {request}")

    def handle_metrics(self, request, headers):
        print(f"received metrics request: {request}")

    def handle_trace(self, request, headers):
        print(f"received trace request: {request}")


sink = GrpcSink(MyHandler())
sink.start()
sink.wait_for_termination()
```

## License

`oteltest` is distributed under the terms of the [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html) license.
