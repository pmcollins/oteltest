# Regression Tests

This directory contains end-to-end regression checks for OpenTelemetry Python
instrumentation behavior with `oteltest`.

The goal is to run a small instrumented workload, capture OTLP telemetry, assert
that expected spans arrive, and compare normalized telemetry against checked-in
golden data. This gives us a smoke/sanity check that can be run against a pinned
release, upstream `main`, or another SDK/instrumentation implementation.

## Mental Model

- A scenario is the workload, such as `sqlite3_basic.py`.
- A subject is the OpenTelemetry SDK/instrumentation set installed for a run.
- Raw telemetry is the JSON captured by `oteltest`.
- Normalized telemetry removes unstable request IDs, timestamps, and transport
  details so two runs can be compared.
- A golden is the approved normalized telemetry for a scenario and profile.

Available subjects:

- `opentelemetry-python-1-41-1` - default pinned PyPI release subject.
- `opentelemetry-python-main` - installs OpenTelemetry Python and contrib
  packages from upstream `main` branches.

Run commands from the repository root. Activate the project environment first so
`oteltest` and the regression tools are on `PATH`:

```shell
source .venv/bin/activate
```

## Comparison Profiles

The runner compares normalized telemetry with a selected profile:

- `strict` is for exact pinned-release checks. It keeps SDK, instrumentation,
  and scope version fields.
- `behavioral` is for comparing upstream development subjects against stable
  telemetry behavior. It drops SDK and instrumentation version fields, drops
  scope version, and treats empty database-name span attributes (`db.name` and
  `db.namespace`) as absent.

Use `strict` when you want to know whether a pinned subject still matches its
exact recorded output. Use `behavioral` for nightly/main checks where version
numbers and other expected cross-version noise should not fail the run.

## Run Existing Checks

Use the runner for local and CI regression checks. It creates a fresh temporary
`oteltest` JSON directory, runs the scenario, normalizes the raw JSON, and
compares it with the selected golden.

Run the default smoke check. With no subject or profile flags, this uses the
default pinned release subject and the `strict` profile:

```shell
python regression_tests/tools/run_regression.py sqlite3_basic
```

Run the pinned release subject against its strict golden:

```shell
python regression_tests/tools/run_regression.py sqlite3_basic \
  --subject opentelemetry-python-1-41-1 \
  --profile strict
```

Run upstream main against the behavioral golden:

```shell
python regression_tests/tools/run_regression.py sqlite3_basic \
  --subject opentelemetry-python-main \
  --profile behavioral
```

Keep raw telemetry after a run by choosing an output directory:

```shell
python regression_tests/tools/run_regression.py sqlite3_basic \
  --subject opentelemetry-python-main \
  --profile behavioral \
  --output-dir /tmp/oteltest-sqlite3-main
```

The output directory must not already contain the scenario output file. For
`sqlite3_basic`, the runner expects `/tmp/oteltest-sqlite3-main/sqlite3_basic.0.json`.

## Generate Or Update Golden Data

Goldens are generated from raw `oteltest` JSON. Use a fresh output directory so
the raw file name is predictable.

First, capture raw telemetry for the subject you want to bless:

```shell
OTELTEST_REGRESSION_SUBJECT=opentelemetry-python-1-41-1 \
  oteltest -j /tmp/oteltest-sqlite3-golden \
  regression_tests/scenarios/sqlite3_basic.py
```

That creates:

```text
/tmp/oteltest-sqlite3-golden/sqlite3_basic.0.json
```

Generate or update the strict golden for a pinned subject:

```shell
python regression_tests/tools/normalize_telemetry.py \
  /tmp/oteltest-sqlite3-golden/sqlite3_basic.0.json \
  --profile strict \
  --output regression_tests/goldens/opentelemetry-python-1-41-1/sqlite3_basic.json
```

Generate or update the behavioral golden:

```shell
python regression_tests/tools/normalize_telemetry.py \
  /tmp/oteltest-sqlite3-golden/sqlite3_basic.0.json \
  --profile behavioral \
  --output regression_tests/goldens/behavioral/sqlite3_basic.json
```

The behavioral golden is usually generated from the latest known-good release.
If upstream `main` intentionally changes behavior and we accept that change,
capture raw telemetry from that subject and regenerate the behavioral golden
from that capture.

After changing a golden, rerun the checks that should pass:

```shell
python regression_tests/tools/run_regression.py sqlite3_basic \
  --subject opentelemetry-python-1-41-1 \
  --profile strict

python regression_tests/tools/run_regression.py sqlite3_basic \
  --subject opentelemetry-python-main \
  --profile behavioral
```

## Inspect Output

Print normalized telemetry without writing a golden:

```shell
python regression_tests/tools/normalize_telemetry.py \
  /tmp/oteltest-sqlite3-golden/sqlite3_basic.0.json \
  --profile behavioral
```

Open captured telemetry in `otelviz`:

```shell
otelviz /tmp/oteltest-sqlite3-golden
```

You can also run `oteltest` directly while developing a scenario:

```shell
oteltest regression_tests/scenarios/sqlite3_basic.py
```

Without `-j`, generated telemetry is written next to the scenario under `json/`.

## Interpreting Failures

A failed scenario assertion usually means the workload crashed, no telemetry was
received, or an expected span disappeared.

A diff means the scenario ran, but normalized telemetry diverged from the
golden. Review the diff before updating a golden. Some divergences are expected
when upstream adds features or changes semantic conventions; others are real
regressions.

If `oteltest` reports that port `4318` is in use, another OTLP HTTP receiver is
already listening on the local default port.

## Add Another Scenario

1. Add a workload under `regression_tests/scenarios/<name>.py`.
2. Follow the shape of `sqlite3_basic.py`: the script body runs the workload,
   and the scenario class supplies requirements, environment, wrapper command,
   and assertions.
3. Add or update a subject in `regression_tests/subjects/` if the scenario needs
   different dependencies.
4. Capture raw telemetry with `oteltest -j`.
5. Generate strict and behavioral goldens.
6. Run the strict pinned-release check and the behavioral main check.
