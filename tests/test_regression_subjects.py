import pytest

from regression_tests.subjects import (
    DEFAULT_SUBJECT,
    SUBJECT_ENV_VAR,
    load_subject,
)


def test_load_default_subject(monkeypatch):
    monkeypatch.delenv(SUBJECT_ENV_VAR, raising=False)

    subject = load_subject()

    assert subject.name == DEFAULT_SUBJECT
    assert subject.name == "opentelemetry-python-1-41-1"
    assert "opentelemetry-api==1.41.1" in subject.requirements
    assert subject.wrapper_command == "opentelemetry-instrument"
    assert (
        subject.environment_variables["OTEL_SERVICE_NAME"] == "regression-sqlite3-basic"
    )


def test_load_subject_from_environment(monkeypatch):
    monkeypatch.setenv(SUBJECT_ENV_VAR, "opentelemetry-python-main")

    subject = load_subject()

    assert subject.name == "opentelemetry-python-main"
    assert any("opentelemetry-python.git@main" in req for req in subject.requirements)
    assert any(
        "opentelemetry-python-contrib.git@main" in req for req in subject.requirements
    )


def test_load_unknown_subject_lists_available_subjects(monkeypatch):
    monkeypatch.setenv(SUBJECT_ENV_VAR, "missing")

    with pytest.raises(ValueError, match="opentelemetry-python-1-41-1"):
        load_subject()
