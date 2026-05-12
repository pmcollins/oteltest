from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

PROFILE_CHOICES = ("strict", "behavioral")
BEHAVIORAL_RESOURCE_EXCLUDES = {
    "telemetry.auto.version",
    "telemetry.sdk.version",
}


def normalize_telemetry(raw: dict[str, Any], profile: str = "strict") -> dict[str, Any]:
    return {
        "traces": normalize_traces(raw.get("trace_requests", []), profile),
        "metrics": [],
        "logs": [],
    }


def normalize_traces(
    trace_requests: list[dict[str, Any]], profile: str
) -> list[dict[str, Any]]:
    traces = []
    for request in trace_requests:
        pbreq = request.get("pbreq", {})
        for resource_span in pbreq.get("resourceSpans", []):
            resource_attrs = normalize_attributes(
                resource_span.get("resource", {}).get("attributes", [])
            )
            if profile == "behavioral":
                resource_attrs = {
                    key: value
                    for key, value in resource_attrs.items()
                    if key not in BEHAVIORAL_RESOURCE_EXCLUDES
                }
            for scope_span in resource_span.get("scopeSpans", []):
                scope = scope_span.get("scope", {})
                normalized_scope = {
                    "name": scope.get("name", ""),
                    "schema_url": scope_span.get("schemaUrl", ""),
                }
                if profile == "strict":
                    normalized_scope["version"] = scope.get("version", "")

                traces.append(
                    {
                        "resource": resource_attrs,
                        "scope": normalized_scope,
                        "spans": [
                            normalize_span(span) for span in scope_span.get("spans", [])
                        ],
                    }
                )
    return traces


def normalize_span(span: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "name": span.get("name", ""),
        "kind": span.get("kind", ""),
        "attributes": normalize_attributes(span.get("attributes", [])),
        "status": normalize_status(span.get("status", {})),
    }

    events = [
        {
            "name": event.get("name", ""),
            "attributes": normalize_attributes(event.get("attributes", [])),
        }
        for event in span.get("events", [])
    ]
    if events:
        normalized["events"] = events

    return normalized


def normalize_status(status: dict[str, Any]) -> dict[str, str]:
    normalized = {}
    if "code" in status:
        normalized["code"] = status["code"]
    if "message" in status:
        normalized["message"] = status["message"]
    return normalized


def normalize_attributes(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        attribute["key"]: normalize_value(attribute.get("value", {}))
        for attribute in sorted(attributes, key=lambda item: item.get("key", ""))
        if "key" in attribute
    }


def normalize_value(value: dict[str, Any]) -> Any:
    for key in (
        "stringValue",
        "intValue",
        "doubleValue",
        "boolValue",
        "bytesValue",
    ):
        if key in value:
            return value[key]

    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        return [normalize_value(item) for item in values]

    if "kvlistValue" in value:
        return normalize_attributes(value["kvlistValue"].get("values", []))

    return value


def dumps_normalized(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def check(raw_path: Path, golden_path: Path, profile: str) -> int:
    actual = dumps_normalized(normalize_telemetry(load_json(raw_path), profile))
    expected = golden_path.read_text(encoding="utf-8")
    if actual == expected:
        return 0

    diff = difflib.unified_diff(
        expected.splitlines(keepends=True),
        actual.splitlines(keepends=True),
        fromfile=str(golden_path),
        tofile=str(raw_path),
    )
    sys.stderr.writelines(diff)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize oteltest telemetry JSON for golden comparisons."
    )
    parser.add_argument("raw_json", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument(
        "--check", type=Path, help="Compare raw JSON to this golden file."
    )
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default="strict",
        help="Normalization profile to apply.",
    )
    args = parser.parse_args()

    if args.check:
        return check(args.raw_json, args.check, args.profile)

    content = dumps_normalized(
        normalize_telemetry(load_json(args.raw_json), args.profile)
    )
    if args.output:
        write_output(args.output, content)
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
