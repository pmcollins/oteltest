import argparse

from oteltest.sink import run_grpc, run_http


def main():
    parser = argparse.ArgumentParser(description="OpenTelemetry Python Tester")
    parser.add_argument("--http", action="store_true", help="Use HTTP instead of gRPC")
    args = parser.parse_args()
    if args.http:
        run_http()
    else:
        run_grpc()


if __name__ == "__main__":
    main()
