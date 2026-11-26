from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from fis_twin.demo import write_demo
from fis_twin.discovery import DiscoveryError, discover
from fis_twin.mapping import load_mapping


CONFIG = Path(__file__).resolve().parents[1] / "config" / "mapping.example.yaml"


def event(case, reader, minute, *, line="L1", key=None, sequence=None):
    time = f"2026-01-01 00:{minute:02}:00+00" if minute is not None else None
    return ("P", case, line, reader, time, key, sequence)


def write_events(path: Path, rows: list[tuple]) -> Path:
    with duckdb.connect() as db:
        db.execute("""
            CREATE TABLE events (site VARCHAR, vehicle VARCHAR, lane VARCHAR, reader VARCHAR,
                observed_at TIMESTAMPTZ, event_key VARCHAR, ordering BIGINT)
        """)
        if rows:
            db.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        db.execute("COPY events TO ? (FORMAT PARQUET)", [str(path)])
    return path


def edges_by_label(graph):
    names = {node["id"]: (node["lineId"], node["label"]) for node in graph["nodes"]}
    return {(names[edge["source"]], names[edge["target"]]): edge for edge in graph["edges"]}


def in_line(source, target, line="L1"):
    return ((line, source), (line, target))


def test_end_to_end_demo_preserves_cross_day_edges_and_isolated_readers(tmp_path: Path) -> None:
    write_demo(tmp_path)
    files = sorted(tmp_path.glob("*.parquet"))
    mapping = load_mapping(CONFIG)
    graph = discover(files, mapping)

    assert discover(list(reversed(files)) + [files[0]], mapping) == graph
    assert len(graph["nodes"]) == 6
    edges = edges_by_label(graph)
    assert set(edges) == {in_line("A", "B"), in_line("B", "A")}
    assert edges[in_line("A", "B")]["medianDurationSeconds"] == 360
    assert edges[in_line("A", "B")]["activeDaysUtc"] == 1
    assert graph["quality"]["firstObservationUtc"] == "2026-01-01T23:58:00.000000Z"
    assert graph["quality"]["excludedPairs"] == {"ambiguous_order": 2}
    assert graph["quality"]["deduplicatedRows"] == 1
    assert graph["quality"]["missingReaderRows"] == 1
    assert graph["variants"]["observableCaseCount"] == 2


def test_weights_ratios_loops_time_ranges_and_tied_sequence(tmp_path: Path) -> None:
    path = write_events(tmp_path / "events.parquet", [
        event("001", "B", 1, sequence=2),
        event("001", "A", 1, sequence=1),
        event("001", "A", 2),
        event("001", "A", 3),
        event("001", "C", 10),
        event("002", "A", 8),
        event("002", "B", 9),
        event("003", "A", 4, line="L2"),
        event("003", "B", 5, line="L2"),
    ])
    graph = discover([path], load_mapping(CONFIG), long_gap_seconds=400)
    edges = edges_by_label(graph)
    assert set(edges) == {
        in_line("A", "B"), in_line("B", "A"), in_line("A", "A"),
        in_line("A", "C"), in_line("A", "B", "L2"),
    }
    branch = edges[in_line("A", "B")]
    assert branch["transitionCount"] == branch["distinctCaseCount"] == 2
    assert branch["minDurationSeconds"] == 0
    assert branch["medianDurationSeconds"] == 30
    assert branch["p90DurationSeconds"] == pytest.approx(54)
    assert branch["outgoingShare"] == pytest.approx(0.5)
    outgoing = [edge["outgoingShare"] for pair, edge in edges.items() if pair[0] == ("L1", "A")]
    assert sum(outgoing) == pytest.approx(1)
    assert edges[in_line("A", "C")]["qualityFlags"] == ["long_gap"]
    assert edges[in_line("A", "C")]["longGapCount"] == 1


def test_unreliable_events_block_pairs_without_crossing_cases(tmp_path: Path) -> None:
    path = write_events(tmp_path / "events.parquet", [
        event("one", "A", 1), event("one", None, 2), event("one", "C", 3),
        event("two", "A", 1), event("two", "B", None), event("two", "C", 3),
        event("three", "A", 1), event("three", "B", 2), event("three", "C", 2),
        event("three", "D", 3), event(None, "E", 2),
        event("four", "X", 1), event("four", "Y", 2, key="conflict"),
        event("four", "Z", 3), event("five", "Q", 2, key="conflict"),
    ])
    graph = discover([path], load_mapping(CONFIG))
    assert graph["edges"] == []
    assert {node["label"] for node in graph["nodes"]} == set("ABCDEQXYZ")
    assert graph["quality"]["excludedPairs"] == {
        "ambiguous_order": 3, "event_id_conflict": 2, "missing_reader": 2,
        "unplaced_event_in_case": 1,
    }
    assert graph["quality"]["ambiguousOrderRows"] == 2
    assert graph["quality"]["casesWithUnplacedEvent"] == 1
    assert graph["quality"]["conflictingEventKeys"] == 1
    assert graph["quality"]["missingCaseRows"] == 1


def test_candidate_requires_opt_in_and_keeps_ties_unresolved(tmp_path: Path) -> None:
    path = write_events(tmp_path / "events.parquet", [
        event("one", "A", 1, sequence=1), event("one", "B", 1, sequence=2),
        event("one", "C", 2),
    ])
    mapping = replace(load_mapping(CONFIG), status="candidate")
    with pytest.raises(DiscoveryError, match="requires --allow-candidate"):
        discover([path], mapping)
    graph = discover([path], mapping, allow_candidate=True)
    assert graph["mappingStatus"] == "candidate"
    assert not graph["edges"]
    assert graph["quality"]["excludedPairs"] == {"ambiguous_order": 2}


def run_discover(source: Path, output: Path) -> subprocess.CompletedProcess:
    return subprocess.run([
        sys.executable, "-m", "fis_twin.cli", "discover", "--input", str(source),
        "--config", str(CONFIG), "--output", str(output),
    ], capture_output=True, text=True, check=False)


def test_refresh_corrects_prior_edge_and_failed_refresh_keeps_graph(tmp_path: Path) -> None:
    source = tmp_path / "input"
    source.mkdir()
    first = write_events(source / "first.parquet", [event("case", "A", 1), event("case", "C", 3)])
    output = tmp_path / "graph.json"
    assert run_discover(source, output).returncode == 0
    before = output.read_bytes()
    assert set(edges_by_label(json.loads(before))) == {in_line("A", "C")}

    write_events(source / "late.parquet", [event("case", "B", 2), event("new case", "D", 4, line="L3")])
    assert run_discover(source, output).returncode == 0
    updated = output.read_bytes()
    assert updated != before
    graph = json.loads(updated)
    assert set(edges_by_label(graph)) == {in_line("A", "B"), in_line("B", "C")}
    assert {node["label"] for node in graph["nodes"]} == set("ABCD")
    assert {node["lineId"] for node in graph["nodes"]} == {"L1", "L3"}
    assert run_discover(source, output).returncode == 0
    assert output.read_bytes() == updated
    first.write_text("broken", encoding="utf-8")
    assert run_discover(source, output).returncode == 1
    assert output.read_bytes() == updated


def test_empty_and_schema_changes(tmp_path: Path) -> None:
    path = write_events(tmp_path / "empty.parquet", [])
    mapping = load_mapping(CONFIG)
    graph = discover([path], mapping)
    assert graph["nodes"] == graph["edges"] == []
    assert graph["quality"]["inputRows"] == 0
    assert graph["variants"]["topVariants"] == []
    with pytest.raises(DiscoveryError, match="contains no Parquet files"):
        empty_directory = tmp_path / "directory"
        empty_directory.mkdir()
        discover([empty_directory], mapping)

    source = tmp_path / "changed.parquet"
    with duckdb.connect() as db:
        db.execute("COPY (SELECT 1 AS vehicle) TO ? (FORMAT PARQUET)", [str(source)])
    with pytest.raises(DiscoveryError, match="case_id"):
        discover([path, source], mapping)
