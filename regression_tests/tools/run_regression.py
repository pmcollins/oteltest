from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from regression_tests.subjects import DEFAULT_SUBJECT, SUBJECT_ENV_VAR, load_subject
from regression_tests.tools.normalize_telemetry import PROFILE_CHOICES, check

SCENARIOS_DIR = ROOT / "regression_tests" / "scenarios"
GOLDENS_DIR = ROOT / "regression_tests" / "goldens"
BEHAVIORAL_BASELINE_SUBJECT = "opentelemetry-python-1-41-1"
BEHAVIORAL_GOLDEN_DIR = f"{BEHAVIORAL_BASELINE_SUBJECT}-behavioral"


def scenario_path(scenario: str) -> Path:
    name = scenario.removesuffix(".py")
    return SCENARIOS_DIR / f"{name}.py"


def raw_output_path(json_dir: Path, scenario: str) -> Path:
    return json_dir / f"{scenario.removesuffix('.py')}.0.json"


def default_golden_path(subject: str, scenario: str, profile: str) -> Path:
    if profile == "behavioral":
        return (
            GOLDENS_DIR / BEHAVIORAL_GOLDEN_DIR / f"{scenario.removesuffix('.py')}.json"
        )
    return GOLDENS_DIR / subject / f"{scenario.removesuffix('.py')}.json"


def run_oteltest(scenario_file: Path, subject: str, json_dir: Path) -> int:
    env = os.environ.copy()
    env[SUBJECT_ENV_VAR] = subject
    result = subprocess.run(
        ["oteltest", "-j", str(json_dir), str(scenario_file)],
        cwd=ROOT,
        env=env,
    )
    return result.returncode


@contextmanager
def output_dir(path: Path | None) -> Iterator[Path]:
    if path is not None:
        path.mkdir(parents=True, exist_ok=True)
        yield path
        return

    with tempfile.TemporaryDirectory(prefix="oteltest-regression-") as temp_dir:
        yield Path(temp_dir)


def run_regression(
    *,
    scenario: str,
    subject: str,
    profile: str,
    golden: Path | None,
    output: Path | None,
) -> int:
    selected_subject = load_subject(subject)
    scenario_file = scenario_path(scenario)
    if not scenario_file.exists():
        print(f"Scenario not found: {scenario_file}", file=sys.stderr)
        return 2

    golden_path = golden or default_golden_path(
        selected_subject.name, scenario, profile
    )
    if not golden_path.exists():
        print(f"Golden file not found: {golden_path}", file=sys.stderr)
        return 2

    with output_dir(output) as json_dir:
        raw_path = raw_output_path(json_dir, scenario)
        if raw_path.exists():
            print(f"Output file already exists: {raw_path}", file=sys.stderr)
            return 2

        print(
            f"Running scenario={scenario_file.name} "
            f"subject={selected_subject.name} profile={profile}",
            flush=True,
        )
        returncode = run_oteltest(scenario_file, selected_subject.name, json_dir)
        if returncode:
            return returncode

        if not raw_path.exists():
            print(
                f"Expected oteltest output was not created: {raw_path}", file=sys.stderr
            )
            return 1

        print(f"Checking {raw_path} against {golden_path}", flush=True)
        return check(raw_path, golden_path, profile)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an oteltest regression scenario and compare it to a golden."
    )
    parser.add_argument("scenario", nargs="?", default="sqlite3_basic")
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default="strict",
        help="Normalization profile to compare with.",
    )
    parser.add_argument("--golden", type=Path, help="Override the golden file path.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for raw oteltest JSON output. Must not already contain this scenario output.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()

    return run_regression(
        scenario=args.scenario,
        subject=args.subject,
        profile=args.profile,
        golden=args.golden,
        output=args.output_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
