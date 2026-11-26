"""Generate a temporary synthetic dataset and measure a discovery CLI run."""

import argparse
import json
from pathlib import Path
import resource
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import duckdb


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2_500_000)
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be positive")
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory() as raw_path, duckdb.connect() as db:
        directory = Path(raw_path)
        start = perf_counter()
        for partition in range(5):
            target = directory / f"synthetic-part-{partition}.parquet"
            db.execute("""
                COPY (
                    SELECT 'Site A' AS site, lpad(case_no::VARCHAR, 7, '0') AS vehicle,
                           'L' || (case_no % 4)::VARCHAR AS lane,
                           'R' || ((case_no // 7 + step * (1 + case_no % 5)) % 24)::VARCHAR AS reader,
                           to_timestamp(1767225600 + case_no % 7200 + step * 7200) AS observed_at,
                           'E' || i::VARCHAR AS event_key, step::BIGINT AS ordering
                    FROM (SELECT i, i // 50 AS case_no, i % 50 AS step FROM range($rows) AS ids(i))
                    WHERE step // 10 = $partition
                ) TO $target (FORMAT PARQUET)
            """, {"rows": args.rows, "partition": partition, "target": str(target)})
        generation = perf_counter() - start
        graph = directory / "graph.json"
        start = perf_counter()
        subprocess.run([
            sys.executable, "-m", "fis_twin.cli", "discover", "--input", str(directory),
            "--config", str(root / "config/mapping.example.yaml"), "--output", str(graph),
        ], check=True)
        discovery = perf_counter() - start
        report = json.loads(graph.read_text(encoding="utf-8"))
        assert report["quality"]["inputRows"] == args.rows
        assert report["quality"]["includedPairs"] == args.rows - (args.rows + 49) // 50
        print(json.dumps({
            "files": report["source"]["fileCount"],
            "rows": report["quality"]["inputRows"],
            "parquetBytes": sum(path.stat().st_size for path in directory.glob("*.parquet")),
            "nodes": len(report["nodes"]),
            "edges": len(report["edges"]),
            "includedPairs": report["quality"]["includedPairs"],
            "generateSeconds": round(generation, 2),
            "discoverySeconds": round(discovery, 2),
            "discoveryPeakRssKiB": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        }, indent=2))


if __name__ == "__main__":
    main()
