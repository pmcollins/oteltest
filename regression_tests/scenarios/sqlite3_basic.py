"""
Regression smoke test: sqlite3 DBAPI instrumentation.

This scenario exercises OpenTelemetry Python's sqlite3 instrumentation through
the auto-instrumentation wrapper. It is intentionally small and dependency-free
apart from OpenTelemetry so it can be used as an early canary for hard crashes in
DBAPI-style instrumentation.
"""

import sqlite3
import sys
import tempfile
from functools import cached_property
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from regression_tests.subjects import load_subject

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="oteltest-sqlite3-basic-") as tmpdir:
        db_path = Path(tmpdir) / "sqlite3_basic.db"

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("create table users (id integer primary key, name text)")
            cur.execute("insert into users (name) values (?)", ("alice",))
            cur.execute("select id, name from users where name = ?", ("alice",))
            rows = cur.fetchall()
            assert rows == [(1, "alice")], rows
        finally:
            conn.close()

    print("dbapi workload complete")


class Sqlite3BasicRegressionOtelTest:
    @cached_property
    def subject(self):
        return load_subject()

    def requirements(self):
        return self.subject.requirements

    def environment_variables(self):
        return self.subject.environment_variables

    def wrapper_command(self):
        return self.subject.wrapper_command

    def on_start(self):
        return 10

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int):
        from oteltest.telemetry import count_spans, get_spans, span_attribute_by_name

        assert (
            returncode == 0
        ), f"script failed with code {returncode}\nstderr:\n{stderr}"
        assert "dbapi workload complete" in stdout
        assert tel.trace_requests, "no trace requests received"

        spans = get_spans(tel)
        assert count_spans(tel) >= 1, "expected at least one sqlite3 span"

        db_spans = [
            span
            for span in spans
            if span_attribute_by_name(span, "db.system") in {"sqlite", "sqlite3"}
        ]
        assert db_spans, "expected at least one span with db.system=sqlite"

        span_names = {span.name.lower() for span in db_spans}
        assert any(
            "select" in name for name in span_names
        ), f"expected a SELECT db span, got: {sorted(span_names)}"

    def is_http(self):
        return True
