import argparse

from oteltest.private import run


def main():
    parser = argparse.ArgumentParser(description="OpenTelemetry Python Tester")

    d_help = "An optional override directory to hold per-script venv directories."
    parser.add_argument(
        "-d", "--venv-parent-dir", type=str, required=False, help=d_help
    )

    j_help = "An optional value to hold the directory into which json telemetry files are written"
    parser.add_argument("-j", "--json-dir", type=str, required=False, help=j_help, default="json")

    parser.add_argument(
        "script_paths",
        nargs="+",
        help="One or more oteltest files or directories containing oteltest scripts",
    )

    args = parser.parse_args()
    run(args.script_paths, args.venv_parent_dir, args.json_dir)


if __name__ == "__main__":
    main()
