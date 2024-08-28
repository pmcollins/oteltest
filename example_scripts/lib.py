import time

from opentelemetry import trace

def trace_loop(loops):
    tracer = trace.get_tracer("my-tracer")
    for i in range(loops):
        with tracer.start_as_current_span("my-span"):
            print(f"loop {i + 1}/{loops}")
            time.sleep(0.5)

