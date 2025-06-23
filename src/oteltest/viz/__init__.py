from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Flask, render_template


def normalize_telemetry(telemetry: Dict[str, Any]) -> Dict[str, List]:
    trace_requests = telemetry.get('trace_requests', [])
    traces = normalize_traces(trace_requests)
    return {'traces': traces}


def normalize_traces(trace_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = {}
    for request in trace_requests:
        pbreq = request.get('pbreq', {})
        for resource_span in pbreq.get('resourceSpans', []):
            resource = resource_span.get('resource', {})
            key = resource_key(resource)

            if key not in merged:
                merged[key] = copy.deepcopy(resource_span)
            else:
                existing = merged[key]
                scope_map = {}

                # Helper function to extract scope identity
                def get_scope_id(spans):
                    scope = spans['scope']
                    scope_name = scope.get('name', '')
                    scope_version = scope.get('version')
                    return scope_name, scope_version

                # Build scope map from existing spans
                for scope_spans in existing.get('scopeSpans', []):
                    scope_map[get_scope_id(scope_spans)] = scope_spans

                # Process new scope spans
                for scope_span in resource_span.get('scopeSpans', []):
                    scope_id = get_scope_id(scope_span)
                    if scope_id in scope_map:
                        scope_map[scope_id].setdefault('spans', []).extend(scope_span.get('spans', []))
                    else:
                        existing.setdefault('scopeSpans', []).append(scope_span)
    return list(merged.values())


def resource_key(resource: Dict[str, Any]) -> Tuple:
    attrs = resource.get('attributes', [])
    return tuple(
        sorted((a['key'], json.dumps(a['value'], sort_keys=True)) for a in attrs if 'key' in a and 'value' in a))


class TraceApp:
    def __init__(self, trace_dir: str):
        self.trace_dir = Path(trace_dir)
        self.app = Flask(__name__)
        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/trace/<path:filename>', 'view_trace', self.view_trace)

    def run(self, **kwargs):
        self.app.run(**kwargs)

    def index(self):
        json_files = self._get_trace_files()
        return render_template('index.html', files=json_files)

    def view_trace(self, filename):
        file_path = self.trace_dir / filename
        data = self._load_trace_file(str(file_path))
        resource_groups = []
        min_start = None
        max_end = None
        # Use the merged telemetry structure
        merged = normalize_telemetry(data)
        for resource_span in merged['traces']:
            resource_attrs = resource_span.get('resource', {}).get('attributes', [])
            # Collect all spans for this resource
            all_spans = []
            for scope_span in resource_span.get('scopeSpans', []):
                all_spans.extend(scope_span.get('spans', []))
            # Group spans by traceId
            spans_by_trace = {}
            for span in all_spans:
                trace_id = span.get('traceId', 'NO_TRACE_ID')
                spans_by_trace.setdefault(trace_id, []).append(span)
                # Track min/max times
                s = int(span['startTimeUnixNano'])
                e = int(span['endTimeUnixNano'])
                if min_start is None or s < min_start:
                    min_start = s
                if max_end is None or e > max_end:
                    max_end = e
            # Build span trees for each traceId
            span_trees_by_trace = {}
            for trace_id, group in spans_by_trace.items():
                span_trees_by_trace[trace_id] = self._build_span_tree(group)
            resource_groups.append({
                'attrs': resource_attrs,
                'span_trees_by_trace': span_trees_by_trace
            })
        if min_start is None:
            min_start = 0
        if max_end is None:
            max_end = 0
        return render_template('trace.html', filename=filename, resource_groups=resource_groups, min_start=min_start,
                               max_end=max_end)

    def _get_trace_files(self):
        return [f.name for f in self.trace_dir.glob('*.json')]

    def _load_trace_file(self, file_path: str) -> Dict:
        with open(file_path) as f:
            return json.load(f)

    def _find_spans(self, data: Dict) -> List[Dict]:
        spans = []
        for request in data.get('trace_requests', []):
            if 'pbreq' in request:
                for resource_span in request['pbreq'].get('resourceSpans', []):
                    for scope_span in resource_span.get('scopeSpans', []):
                        spans.extend(scope_span.get('spans', []))
        return spans

    def _build_span_tree(self, spans: List[Dict]) -> List[Dict]:
        span_map = {span['spanId']: span for span in spans}
        root_spans = []

        # Clear any previous children/depth to avoid side effects
        for span in spans:
            span.pop('children', None)
            span.pop('depth', None)

        def assign_depth(span, depth):
            span['depth'] = depth
            for child in [s for s in spans if s.get('parentSpanId') == span.get('spanId')]:
                if 'children' not in span:
                    span['children'] = []
                span['children'].append(child)
                assign_depth(child, depth + 1)

        for span in spans:
            if 'parentSpanId' not in span or not span['parentSpanId'] or span['parentSpanId'] not in span_map:
                assign_depth(span, 0)
                root_spans.append(span)

        return root_spans
