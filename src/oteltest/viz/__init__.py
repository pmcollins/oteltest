import json
from pathlib import Path
from typing import Dict, List
from flask import Flask, render_template
import argparse


class TraceApp:
    def __init__(self, trace_dir: str):
        self.trace_dir = Path(trace_dir)
        self.app = Flask(__name__)
        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/trace/<path:filename>', 'view_trace', self.view_trace)

    def load_trace_file(self, file_path: str) -> Dict:
        with open(file_path, 'r') as f:
            return json.load(f)

    def find_spans(self, data: Dict) -> List[Dict]:
        spans = []
        for request in data.get('trace_requests', []):
            if 'pbreq' in request:
                for resource_span in request['pbreq'].get('resourceSpans', []):
                    for scope_span in resource_span.get('scopeSpans', []):
                        spans.extend(scope_span.get('spans', []))
        return spans

    def build_span_tree(self, spans: List[Dict]) -> List[Dict]:
        span_map = {span['spanId']: span for span in spans}
        root_spans = []

        for span in spans:
            if 'parentSpanId' not in span:
                root_spans.append(span)
            else:
                parent = span_map.get(span['parentSpanId'])
                if parent:
                    if 'children' not in parent:
                        parent['children'] = []
                    parent['children'].append(span)

        return root_spans

    def get_trace_files(self):
        return [f.name for f in self.trace_dir.glob('*.json')]

    def index(self):
        json_files = self.get_trace_files()
        return render_template('index.html', files=json_files)

    def view_trace(self, filename):
        file_path = self.trace_dir / filename
        data = self.load_trace_file(str(file_path))
        spans = self.find_spans(data)
        root_spans = self.build_span_tree(spans)
        return render_template('trace.html', filename=filename, spans=root_spans)

    def run(self, **kwargs):
        self.app.run(**kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List trace JSON files in a directory.")
    parser.add_argument("trace_dir", type=str, help="Directory containing trace JSON files.")
    args = parser.parse_args()
    trace_app = TraceApp(args.trace_dir)
    trace_app.run(debug=True, port=5000)
