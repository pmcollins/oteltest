from regression_tests.tools.normalize_telemetry import normalize_telemetry


def test_normalize_telemetry_removes_unstable_span_fields():
    raw = {
        "trace_requests": [
            {
                "pbreq": {
                    "resourceSpans": [
                        {
                            "resource": {
                                "attributes": [
                                    {
                                        "key": "service.name",
                                        "value": {"stringValue": "svc"},
                                    }
                                ]
                            },
                            "scopeSpans": [
                                {
                                    "scope": {"name": "scope", "version": "1.0"},
                                    "schemaUrl": "https://example.test/schema",
                                    "spans": [
                                        {
                                            "traceId": "random",
                                            "spanId": "random",
                                            "name": "select",
                                            "kind": "SPAN_KIND_CLIENT",
                                            "startTimeUnixNano": "123",
                                            "endTimeUnixNano": "456",
                                            "attributes": [
                                                {
                                                    "key": "db.system",
                                                    "value": {"stringValue": "sqlite"},
                                                }
                                            ],
                                            "status": {},
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
                "headers": {"Content-Length": "123"},
                "test_elapsed_ms": 10,
            }
        ]
    }

    normalized = normalize_telemetry(raw)

    assert normalized == {
        "traces": [
            {
                "resource": {"service.name": "svc"},
                "scope": {
                    "name": "scope",
                    "version": "1.0",
                    "schema_url": "https://example.test/schema",
                },
                "spans": [
                    {
                        "name": "select",
                        "kind": "SPAN_KIND_CLIENT",
                        "attributes": {"db.system": "sqlite"},
                        "status": {},
                    }
                ],
            }
        ],
        "metrics": [],
        "logs": [],
    }


def test_behavioral_profile_removes_version_noise():
    raw = {
        "trace_requests": [
            {
                "pbreq": {
                    "resourceSpans": [
                        {
                            "resource": {
                                "attributes": [
                                    {
                                        "key": "telemetry.sdk.version",
                                        "value": {"stringValue": "1.41.1"},
                                    },
                                    {
                                        "key": "telemetry.auto.version",
                                        "value": {"stringValue": "0.62b1"},
                                    },
                                    {
                                        "key": "telemetry.sdk.name",
                                        "value": {"stringValue": "opentelemetry"},
                                    },
                                ]
                            },
                            "scopeSpans": [
                                {
                                    "scope": {"name": "scope", "version": "1.0"},
                                    "schemaUrl": "https://example.test/schema",
                                    "spans": [
                                        {
                                            "name": "select",
                                            "kind": "SPAN_KIND_CLIENT",
                                            "attributes": [],
                                            "status": {},
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
            }
        ]
    }

    normalized = normalize_telemetry(raw, profile="behavioral")

    assert normalized["traces"][0]["resource"] == {
        "telemetry.sdk.name": "opentelemetry"
    }
    assert normalized["traces"][0]["scope"] == {
        "name": "scope",
        "schema_url": "https://example.test/schema",
    }


def test_behavioral_profile_removes_empty_db_name_attributes():
    raw = {
        "trace_requests": [
            {
                "pbreq": {
                    "resourceSpans": [
                        {
                            "resource": {"attributes": []},
                            "scopeSpans": [
                                {
                                    "scope": {"name": "scope", "version": "1.0"},
                                    "spans": [
                                        {
                                            "name": "select",
                                            "kind": "SPAN_KIND_CLIENT",
                                            "attributes": [
                                                {
                                                    "key": "custom.empty",
                                                    "value": {"stringValue": ""},
                                                },
                                                {
                                                    "key": "db.name",
                                                    "value": {"stringValue": ""},
                                                },
                                                {
                                                    "key": "db.namespace",
                                                    "value": {"stringValue": ""},
                                                },
                                                {
                                                    "key": "db.statement",
                                                    "value": {
                                                        "stringValue": "select 1"
                                                    },
                                                },
                                            ],
                                            "status": {},
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
            }
        ]
    }

    strict_normalized = normalize_telemetry(raw)
    behavioral_normalized = normalize_telemetry(raw, profile="behavioral")

    assert strict_normalized["traces"][0]["spans"][0]["attributes"] == {
        "custom.empty": "",
        "db.name": "",
        "db.namespace": "",
        "db.statement": "select 1",
    }
    assert behavioral_normalized["traces"][0]["spans"][0]["attributes"] == {
        "custom.empty": "",
        "db.statement": "select 1",
    }
