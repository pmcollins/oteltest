from pathlib import Path

from regression_tests.tools.run_regression import (
    default_golden_path,
    parse_args,
    raw_output_path,
    scenario_path,
)


def test_scenario_path_accepts_name_or_file_name():
    assert (
        scenario_path("sqlite3_basic")
        == Path("regression_tests/scenarios/sqlite3_basic.py").resolve()
    )
    assert (
        scenario_path("sqlite3_basic.py")
        == Path("regression_tests/scenarios/sqlite3_basic.py").resolve()
    )


def test_raw_output_path_is_deterministic_for_fresh_output_dir(tmp_path):
    assert (
        raw_output_path(tmp_path, "sqlite3_basic") == tmp_path / "sqlite3_basic.0.json"
    )


def test_default_golden_path_for_behavioral_profile():
    assert (
        default_golden_path("opentelemetry-python-main", "sqlite3_basic", "behavioral")
        == Path(
            "regression_tests/goldens/"
            "opentelemetry-python-1-41-1-behavioral/sqlite3_basic.json"
        ).resolve()
    )


def test_default_golden_path_for_strict_profile():
    assert (
        default_golden_path("opentelemetry-python-1-41-1", "sqlite3_basic", "strict")
        == Path(
            "regression_tests/goldens/opentelemetry-python-1-41-1/sqlite3_basic.json"
        ).resolve()
    )


def test_cli_defaults_to_strict_profile():
    args = parse_args(["sqlite3_basic"])

    assert args.profile == "strict"
