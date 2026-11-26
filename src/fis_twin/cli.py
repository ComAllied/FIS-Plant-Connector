"""Local commands for the FIS event-log workflow."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from typing import Any

import duckdb

from .demo import write_demo
from .mapping import MappingError, load_mapping
from .profile import ProfileError, profile_parquet


def write_json(output: Path, report: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(report, file, indent=2, ensure_ascii=False, allow_nan=False)
            file.write("\n")
            file.close()
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile", help="Write a local aggregate Parquet report.")
    profile.add_argument(
        "--input", type=Path, action="append", required=True,
        help="Local Parquet file or directory, repeatable. Directories are scanned recursively.",
    )
    profile.add_argument("--config", type=Path, help="Optional versioned YAML mapping.")
    profile.add_argument("--output", type=Path, required=True, help="Local JSON report path.")
    demo = commands.add_parser("demo-data", help="Generate two synthetic Parquet files.")
    demo.add_argument("--output", type=Path, required=True, help="Local output directory.")
    args = parser.parse_args(argv)

    try:
        if args.command == "demo-data":
            write_demo(args.output)
            print("Synthetic Parquet files written.")
            return 0
        if args.output.suffix.lower() != ".json":
            raise ProfileError("Profile output must be a .json file.")
        if args.config and args.output.resolve() == args.config.resolve():
            raise ProfileError("Profile output must differ from the mapping file.")
        mapping = load_mapping(args.config) if args.config else None
        write_json(args.output, profile_parquet(args.input, mapping))
        print("Parquet profile written.")
        return 0
    except (ProfileError, MappingError) as error:
        print(f"Error: {error}", file=sys.stderr)
    except FileExistsError:
        print("Error: Output already exists or cannot be created.", file=sys.stderr)
    except (OSError, duckdb.Error):
        print("Error: Unable to access local input or output.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
