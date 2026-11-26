"""Local commands for the FIS event-log workflow."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from typing import Any

import duckdb
from filelock import FileLock

from .demo import write_demo
from .discovery import DiscoveryError, discover
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
    graph = commands.add_parser("discover", help="Build or refresh a directed production graph.")
    for command in (profile, graph):
        command.add_argument(
            "--input", type=Path, action="append", required=True,
            help="Local Parquet file or directory, repeatable. Directories are scanned recursively.",
        )
        command.add_argument("--config", type=Path, required=command is graph, help="Versioned YAML mapping.")
        command.add_argument("--output", type=Path, required=True, help="Local JSON output path.")
    graph.add_argument("--allow-candidate", action="store_true", help="Build a labeled provisional graph.")
    graph.add_argument("--long-gap-seconds", type=float, default=86_400)
    demo = commands.add_parser("demo-data", help="Generate two synthetic Parquet files.")
    demo.add_argument("--output", type=Path, required=True, help="Local output directory.")
    serve = commands.add_parser("serve", help="Open the built frontend on local loopback.")
    serve.add_argument("--graph", type=Path, required=True, help="Current graph.json file.")
    serve.add_argument("--frontend", type=Path, default=Path("frontend/dist"))
    serve.add_argument("--port", type=int, default=3000)
    args = parser.parse_args(argv)

    try:
        if args.command == "demo-data":
            write_demo(args.output)
            print("Synthetic Parquet files written.")
            return 0
        if args.command == "serve":
            if not (args.frontend / "index.html").is_file():
                raise ProfileError("Frontend build missing. Run npm ci and npm run build in frontend.")
            try:
                import uvicorn
                from .web import create_app
            except ModuleNotFoundError:
                raise ProfileError("Install the optional web dependencies with pip install -e '.[web]'.") from None
            uvicorn.run(create_app(args.graph, args.frontend), host="127.0.0.1", port=args.port)
            return 0
        if args.output.suffix.lower() != ".json":
            raise ProfileError("Output must be a .json file.")
        if args.config and args.output.resolve() == args.config.resolve():
            raise ProfileError("Output must differ from the mapping file.")
        mapping = load_mapping(args.config) if args.config else None
        if args.command == "discover":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with FileLock(args.output.with_name(args.output.name + ".lock")):
                result = discover(
                    args.input, mapping, allow_candidate=args.allow_candidate,
                    long_gap_seconds=args.long_gap_seconds,
                )
                write_json(args.output, result)
            print("Production graph written.")
            return 0
        write_json(args.output, profile_parquet(args.input, mapping))
        print("Parquet profile written.")
        return 0
    except (ProfileError, MappingError, DiscoveryError) as error:
        print(f"Error: {error}", file=sys.stderr)
    except FileExistsError:
        print("Error: Output already exists or cannot be created.", file=sys.stderr)
    except (OSError, duckdb.Error):
        print("Error: Unable to access local input or output.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
