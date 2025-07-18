import pytest
from oteltest.viz import TraceApp

def test_process_traces_merges_and_times():
    app = TraceApp(trace_dir=".")
    traces = [
        {
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "svc"}}]},
            "scopeSpans": [
                {
                    "scope": {"name": "scope", "version": "1.0"},
                    "spans": [
                        {"spanId": "1", "traceId": "abc", "startTimeUnixNano": 100, "endTimeUnixNano": 200},
                        {"spanId": "2", "traceId": "abc", "startTimeUnixNano": 150, "endTimeUnixNano": 250},
                    ],
                }
            ],
        }
    ]
    groups, min_start, max_end = app.process_traces(traces)
    assert isinstance(groups, list)
    assert min_start == 100
    assert max_end == 250
    assert len(groups) == 1
    assert "span_trees_by_trace" in groups[0]
    assert "abc" in groups[0]["span_trees_by_trace"]
    assert len(groups[0]["span_trees_by_trace"]["abc"]) == 2


def test_process_metrics_grouping():
    app = TraceApp(trace_dir=".")
    metrics = [
        {
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "svc"}}]},
            "scopeMetrics": [
                {
                    "scope": {"name": "scope", "version": "1.0"},
                    "metrics": [
                        {"name": "metric1", "sum": 42}
                    ]
                }
            ]
        }
    ]
    groups = app.process_metrics(metrics)
    assert isinstance(groups, list)
    assert len(groups) == 1
    assert groups[0]["attrs"][0]["key"] == "service.name"
    assert len(groups[0]["scope_metrics_list"]) == 1
    assert groups[0]["scope_metrics_list"][0]["metrics"][0]["name"] == "metric1"


def test_view_telemetry_renders(monkeypatch, tmp_path):
    app = TraceApp(trace_dir=tmp_path)
    fake_data = {
        "trace_requests": [],
        "metric_requests": []
    }
    (tmp_path / "file.json").write_text("{}")
    monkeypatch.setattr(app, "_load_trace_file", lambda path: fake_data)
    monkeypatch.setattr("oteltest.viz.render_template", lambda *a, **kw: kw)
    result = app.view_telemetry("file.json")
    assert "resource_groups" in result
    assert "metric_groups" in result
    assert "min_start" in result
    assert "max_end" in result
    assert result["filename"] == "file.json"
