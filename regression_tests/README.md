# Regression Tests

This directory contains end-to-end regression scenarios for checking OpenTelemetry
Python instrumentation behavior with `oteltest`.

The first goal is crash/smoke coverage plus normalized golden comparison: run a
realistic instrumented workload, capture OTLP telemetry, assert that expected
spans arrive, and compare stable telemetry shape against checked-in goldens.

Scenarios are deliberately separate from subjects:

- A scenario is the workload, such as `sqlite3_basic.py`.
- A subject is the OpenTelemetry SDK/instrumentation set installed for that run.

Available subjects:

- `opentelemetry-python-1-41-1` - default pinned PyPI release subject.
- `opentelemetry-python-main` - installs OpenTelemetry Python and contrib
  packages from upstream `main` branches.

## Run a Scenario

For local and CI regression checks, use the runner. It creates a fresh oteltest
JSON output directory, runs the scenario, then compares the generated raw JSON to
the selected golden:

```shell
source .venv/bin/activate
python regression_tests/tools/run_regression.py sqlite3_basic
```

Run upstream main against the behavioral golden:

```shell
source .venv/bin/activate
python regression_tests/tools/run_regression.py sqlite3_basic \
  --subject opentelemetry-python-main \
  --profile behavioral
```

You can still run `oteltest` directly while developing a scenario:

```shell
source .venv/bin/activate
oteltest regression_tests/scenarios/sqlite3_basic.py
```

Scenarios run against the pinned release subject by default. Select another
subject with `OTELTEST_REGRESSION_SUBJECT`:

```shell
OTELTEST_REGRESSION_SUBJECT=opentelemetry-python-main \
  oteltest regression_tests/scenarios/sqlite3_basic.py
```

Generated telemetry is written next to the scenario under `json/` and can be
viewed with:

```shell
otelviz regression_tests/scenarios/json
```

## Golden Data

Raw telemetry contains unstable IDs, timestamps, request timing, and transport
headers. Normalize raw output before comparing it with checked-in golden data.

Use the `strict` profile for pinned-release checks. It keeps SDK and
instrumentation versions:

```shell
python regression_tests/tools/normalize_telemetry.py \
  regression_tests/scenarios/json/sqlite3_basic.4.json \
  --profile strict \
  --output regression_tests/goldens/opentelemetry-python-1-41-1/sqlite3_basic.json
```

Check a pinned-release run against the strict golden:

```shell
python regression_tests/tools/normalize_telemetry.py \
  regression_tests/scenarios/json/sqlite3_basic.4.json \
  --profile strict \
  --check regression_tests/goldens/opentelemetry-python-1-41-1/sqlite3_basic.json
```

Use the `behavioral` profile when comparing an upstream development subject
against stable telemetry behavior. It drops SDK and instrumentation version
fields that are expected to change across releases. It also treats empty
database-name span attributes (`db.name` and `db.namespace`) as absent, since
some DBAPI versions emit empty strings while newer semantic-convention helpers
omit them:

```shell
python regression_tests/tools/normalize_telemetry.py \
  regression_tests/scenarios/json/sqlite3_basic.5.json \
  --profile behavioral \
  --check regression_tests/goldens/behavioral/sqlite3_basic.json
```

That last command is the current "upstream main did not diverge behaviorally"
check after running the scenario with
`OTELTEST_REGRESSION_SUBJECT=opentelemetry-python-main`.
