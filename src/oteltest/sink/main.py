import argparse
import logging

from oteltest.sink import run_grpc, run_http


def main():
    parser = argparse.ArgumentParser(description="OpenTelemetry Python Tester")
    parser.add_argument("--http", action="store_true", help="Use HTTP instead of gRPC")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("otelsink")

    if args.http:
        run_http(logger)
    else:
        run_grpc(logger)


if __name__ == "__main__":
    main()
