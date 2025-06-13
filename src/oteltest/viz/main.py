import argparse

from oteltest.viz import TraceApp


def main():
    parser = argparse.ArgumentParser(description="List trace JSON files in a directory.")
    parser.add_argument("trace_dir", type=str, help="Directory containing trace JSON files.")
    args = parser.parse_args()
    trace_app = TraceApp(args.trace_dir)
    trace_app.run(debug=True, port=8888)


if __name__ == "__main__":
    main()

