"""
Regression smoke test: SQLAlchemy instrumentation over sqlite.

This scenario covers SQLAlchemy's DB layer without requiring an external
database service.
"""

import sys
from functools import cached_property
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from regression_tests.subjects import load_subject

if __name__ == "__main__":
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.execute(text("create table users (id integer primary key, name text)"))
            conn.execute(
                text("insert into users (name) values (:name)"), {"name": "alice"}
            )
            rows = conn.execute(
                text("select id, name from users where name = :name"),
                {"name": "alice"},
            ).fetchall()
            assert rows == [(1, "alice")], rows
    finally:
        engine.dispose()

    print("sqlalchemy workload complete")


class SqlalchemySqliteBasicRegressionOtelTest:
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
        assert "sqlalchemy workload complete" in stdout
        assert tel.trace_requests, "no trace requests received"

        spans = get_spans(tel)
        assert count_spans(tel) >= 1, "expected at least one SQLAlchemy span"

        db_spans = [
            span
            for span in spans
            if span_attribute_by_name(span, "db.system") in {"sqlite", "sqlite3"}
            or span_attribute_by_name(span, "db.system.name") in {"sqlite", "sqlite3"}
        ]
        assert db_spans, "expected at least one span with db.system=sqlite"

        span_names = {span.name.lower() for span in db_spans}
        assert any(
            "select" in name for name in span_names
        ), f"expected a SELECT db span, got: {sorted(span_names)}"

    def is_http(self):
        return True
