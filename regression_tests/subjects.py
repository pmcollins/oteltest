from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SUBJECT = "opentelemetry-python-1-41-1"
SUBJECT_ENV_VAR = "OTELTEST_REGRESSION_SUBJECT"
SUBJECTS_DIR = Path(__file__).parent / "subjects"


@dataclass(frozen=True)
class Subject:
    name: str
    requirements: list[str]
    environment_variables: dict[str, str]
    wrapper_command: str | None


def load_subject(name: str | None = None) -> Subject:
    subject_name = name or os.environ.get(SUBJECT_ENV_VAR, DEFAULT_SUBJECT)
    path = SUBJECTS_DIR / f"{subject_name}.json"
    if not path.exists():
        available = ", ".join(sorted(file.stem for file in SUBJECTS_DIR.glob("*.json")))
        raise ValueError(
            f"Unknown regression subject '{subject_name}'. Available subjects: {available}"
        )

    with path.open(encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)

    return Subject(
        name=data.get("name", subject_name),
        requirements=list(data["requirements"]),
        environment_variables=dict(data.get("environment_variables", {})),
        wrapper_command=data.get("wrapper_command"),
    )
