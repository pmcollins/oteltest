import json
from pathlib import Path
from typing import Dict, List

from flask import Flask, render_template


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
        spans = self._find_spans(data)
        # Group spans by traceId
        spans_by_trace = {}
        for span in spans:
            trace_id = span.get('traceId', 'NO_TRACE_ID')
            spans_by_trace.setdefault(trace_id, []).append(span)
        # Build span trees for each traceId
        span_trees_by_trace = {}
        for trace_id, group in spans_by_trace.items():
            span_trees_by_trace[trace_id] = self._build_span_tree(group)
        # Compute min start and max end time for all spans
        if spans:
            min_start = min(int(span['startTimeUnixNano']) for span in spans)
            max_end = max(int(span['endTimeUnixNano']) for span in spans)
        else:
            min_start = 0
            max_end = 0
        return render_template('trace.html', filename=filename, span_trees_by_trace=span_trees_by_trace, min_start=min_start, max_end=max_end)

    def _get_trace_files(self):
        return [f.name for f in self.trace_dir.glob('*.json')]

    def _load_trace_file(self, file_path: str) -> Dict:
        with open(file_path, 'r') as f:
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
