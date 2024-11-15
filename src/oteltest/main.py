import argparse
import logging

from oteltest.private import run
from oteltest.version import __version__ as version

def main():
    parser = argparse.ArgumentParser(description=f"Version {version}")

    d_help = "An optional override directory to hold per-script venv directories."
    parser.add_argument(
        "-d", "--venv-parent-dir", type=str, required=False, help=d_help
    )

    j_help = "An optional value to hold the directory into which json telemetry files are written"
    parser.add_argument(
        "-j", "--json-dir", type=str, required=False, help=j_help, default="json"
    )

    v_help = "Enable verbose output; include this flag for detailed logging."
    parser.add_argument("-v", "--verbose", action="store_true", help=v_help)

    parser.add_argument(
        "script_paths",
        nargs="+",
        help="One or more oteltest files or directories containing oteltest scripts",
    )

    args = parser.parse_args()

    if args.verbose:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    logging.basicConfig(
        level=logging_level,
        format="> %(message)s",
    )
    logger = logging.getLogger("oteltest")

    run(args.script_paths, args.venv_parent_dir, args.json_dir, logger)


if __name__ == "__main__":
    main()
