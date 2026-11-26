"""Build a deterministic directly-follows graph from a local Parquet snapshot."""

from dataclasses import asdict
from hashlib import file_digest, sha256
import json
import math
from pathlib import Path
from typing import Any

import duckdb

from .database import local_database
from .mapping import Field, Mapping
from .profile import (
    ProfileError, identifier, invalid, mapping_issues, parquet_columns, parquet_paths,
    parquet_storage_schema,
)


class DiscoveryError(ValueError):
    """The graph cannot be computed from a consistent, interpretable snapshot."""


INTEGER_TYPES = {
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
}
IDENTITY_FIELDS = ("case_id", "reader_id", "event_id")


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def file_versions(paths: list[Path]) -> list[tuple[Path, int, int, int, int]]:
    versions = []
    for path in paths:
        stat = path.stat()
        versions.append((path, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns))
    return versions


def validate_mapping(mapping: Mapping, allow_candidate: bool, long_gap_seconds: float) -> None:
    if mapping.status == "candidate" and not allow_candidate:
        raise DiscoveryError("Candidate mapping requires --allow-candidate for a provisional graph.")
    if not math.isfinite(long_gap_seconds) or long_gap_seconds <= 0:
        raise DiscoveryError("Long-gap threshold must be a finite positive number of seconds.")
    if mapping.fields["event_time"].types != ("TIMESTAMP WITH TIME ZONE",):
        raise DiscoveryError("Discovery requires a timezone-aware event timestamp.")
    for name, field in mapping.fields.items():
        if name in IDENTITY_FIELDS:
            if any(kind not in INTEGER_TYPES | {"VARCHAR", "UUID"} for kind in field.types):
                raise DiscoveryError(f"{name} requires text, UUID or integer identity components.")
        elif len(field.columns) != 1:
            raise DiscoveryError(f"{name} must map to exactly one source column.")
        elif name == "sequence_id" and field.types[0] not in INTEGER_TYPES:
            raise DiscoveryError("sequence_id requires an integer source column.")


def safe_value(field: Field | None, output_type: str = "VARCHAR") -> str:
    if field is None:
        return f"NULL::{output_type}"
    column = identifier(field.columns[0])
    return f"CASE WHEN NOT {invalid(field)} THEN CAST({column} AS {output_type}) END"


def identity(field: Field | None) -> str:
    if field is None:
        return "NULL::VARCHAR"
    components = ", ".join(f"CAST({identifier(name)} AS VARCHAR)" for name in field.columns)
    return f"CASE WHEN NOT {invalid(field)} THEN CAST(to_json(list_value({components})) AS VARCHAR) END"


def load_events(db: duckdb.DuckDBPyConnection, paths: list[Path], mapping: Mapping) -> int:
    for index, path in enumerate(paths, start=1):
        try:
            issues = mapping_issues(parquet_columns(db, path), mapping)
            storage = parquet_storage_schema(db, path)
        except duckdb.Error:
            raise DiscoveryError(f"Unable to read Parquet input file {index}.") from None
        if issues:
            details = ", ".join(f"{issue['field']} ({issue['code']})" for issue in issues)
            raise DiscoveryError(f"Mapping incompatible with input file {index}: {details}. Run profile.")
        time_column = mapping.fields["event_time"].columns[0]
        if any(
            field[0] == time_column and "NANOS=NanoSeconds" in (field[4] or "")
            for field in storage
        ):
            raise DiscoveryError(
                "Timezone-aware nanosecond timestamps cannot be read losslessly by this engine."
            )

    fields = mapping.fields
    reader = fields["reader_id"]
    use_ordering = mapping.status != "candidate"
    expressions = {
        "case_key": identity(fields["case_id"]),
        "reader_key": identity(reader),
        "observed": safe_value(fields["event_time"], "TIMESTAMPTZ"),
        "event_key": identity(fields.get("event_id") if use_ordering else None),
        "sequence_no": safe_value(fields.get("sequence_id") if use_ordering else None, "HUGEINT"),
        "plant": safe_value(fields.get("plant_id")),
        "line": safe_value(fields.get("line_id")),
        "area": safe_value(fields.get("area_id")),
        "label": safe_value(fields.get("reader_name")),
        "description": safe_value(fields.get("description")),
        "fallback_label": f"CAST({identifier(reader.columns[-1])} AS VARCHAR)",
    }
    projection = ", ".join(f"{expression} AS {name}" for name, expression in expressions.items())
    sources = " UNION ALL ".join(
        f"SELECT {projection} FROM read_parquet(?, hive_partitioning=false)" for _ in paths
    )
    db.execute(f"CREATE TEMP TABLE input_events AS {sources}", [str(path) for path in paths])
    input_rows = db.execute("SELECT count(*) FROM input_events").fetchall()[0][0]
    db.execute("""
        CREATE TEMP TABLE events AS
        WITH deduplicated AS (
            SELECT DISTINCT * FROM input_events WHERE event_key IS NOT NULL
            UNION ALL
            SELECT * FROM input_events WHERE event_key IS NULL
        ), event_conflicts AS (
            SELECT event_key, count(*) > 1 AS conflict
            FROM deduplicated WHERE event_key IS NOT NULL GROUP BY event_key
        )
        SELECT deduplicated.*, coalesce(conflict, false) AS event_conflict
        FROM deduplicated LEFT JOIN event_conflicts USING (event_key)
    """)
    db.execute("DROP TABLE input_events")
    db.execute("""
        CREATE TEMP TABLE ordered_events AS
        WITH time_groups AS (
            SELECT case_key, observed,
                   count(*) = 1 OR count(DISTINCT sequence_no) = count(*) AS reliable
            FROM events WHERE case_key IS NOT NULL AND observed IS NOT NULL
            GROUP BY case_key, observed
        ), unplaced_cases AS (
            SELECT DISTINCT case_key FROM events WHERE case_key IS NOT NULL AND observed IS NULL
        )
        SELECT events.case_key, events.observed, sequence_no, reader_key, event_conflict, reliable,
               unplaced_cases.case_key IS NOT NULL AS has_unplaced_event
        FROM events JOIN time_groups USING (case_key, observed)
        LEFT JOIN unplaced_cases USING (case_key)
    """)
    db.execute("""
        CREATE TEMP TABLE pairs AS
        WITH neighbors AS (
            SELECT *, lead(reader_key) OVER w AS target,
                   lead(observed) OVER w AS next_time,
                   lead(reliable) OVER w AS next_reliable,
                   lead(event_conflict) OVER w AS next_conflict
            FROM ordered_events
            WINDOW w AS (PARTITION BY case_key ORDER BY observed, sequence_no)
        )
        SELECT case_key, reader_key AS source, target, observed,
               CASE WHEN has_unplaced_event THEN 'unplaced_event_in_case'
                    WHEN NOT (reliable AND next_reliable) THEN 'ambiguous_order'
                    WHEN event_conflict OR next_conflict THEN 'event_id_conflict'
                    WHEN reader_key IS NULL OR target IS NULL THEN 'missing_reader'
               END AS excluded_reason,
               date_diff('microseconds', observed, next_time) / 1000000.0 AS duration
        FROM neighbors WHERE next_time IS NOT NULL
    """)
    return input_rows


def records(db: duckdb.DuckDBPyConnection, sql: str, parameters: list[Any] | None = None) -> list[dict]:
    cursor = db.execute(sql, parameters)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def graph_data(
    db: duckdb.DuckDBPyConnection, mapping: Mapping, input_rows: int, long_gap_seconds: float
) -> dict[str, Any]:
    nodes = records(db, """
        SELECT sha256(reader_key) AS id,
               CASE WHEN count(DISTINCT label) = 1 THEN min(label) ELSE min(fallback_label) END AS label,
               CASE WHEN count(DISTINCT plant) = 1 THEN min(plant) END AS "plantId",
               CASE WHEN count(DISTINCT line) = 1 THEN min(line) END AS "lineId",
               CASE WHEN count(DISTINCT area) = 1 THEN min(area) END AS "areaId",
               CASE WHEN count(DISTINCT description) = 1 THEN min(description) END AS description,
               count(*) AS "eventCount", count(DISTINCT case_key) AS "distinctCaseCount",
               list_filter([
                   CASE WHEN count(DISTINCT label) > 1 THEN 'label_conflict' END,
                   CASE WHEN count(DISTINCT plant) > 1 THEN 'plant_conflict' END,
                   CASE WHEN count(DISTINCT line) > 1 THEN 'line_conflict' END,
                   CASE WHEN count(DISTINCT area) > 1 THEN 'area_conflict' END,
                   CASE WHEN count(DISTINCT description) > 1 THEN 'description_conflict' END
               ], flag -> flag IS NOT NULL) AS "qualityFlags"
        FROM events WHERE reader_key IS NOT NULL GROUP BY reader_key ORDER BY id
    """)
    edges = records(db, """
        WITH aggregate_edges AS (
            SELECT sha256(source) AS source, sha256(target) AS target, count(*) AS "transitionCount",
                   count(DISTINCT case_key) AS "distinctCaseCount",
                   count(DISTINCT floor(epoch(observed) / 86400)) AS "activeDaysUtc",
                   min(duration) AS "minDurationSeconds",
                   median(duration) AS "medianDurationSeconds",
                   quantile_cont(duration, 0.9) AS "p90DurationSeconds",
                   max(duration) AS "maxDurationSeconds",
                   count(*) FILTER (WHERE duration > ?) AS "longGapCount"
            FROM pairs WHERE excluded_reason IS NULL GROUP BY pairs.source, pairs.target
        )
        SELECT sha256(source || target) AS id, *,
               "transitionCount"::DOUBLE / sum("transitionCount") OVER (PARTITION BY source) AS "outgoingShare",
               CASE WHEN "longGapCount" > 0 THEN ['long_gap'] ELSE [] END AS "qualityFlags"
        FROM aggregate_edges ORDER BY source, target
    """, [long_gap_seconds])
    quality = records(db, """
        SELECT ? AS "inputRows", count(*) AS "normalizedRows",
               ? - count(*) AS "deduplicatedRows",
               count(*) FILTER (WHERE case_key IS NULL) AS "missingCaseRows",
               count(*) FILTER (WHERE reader_key IS NULL) AS "missingReaderRows",
               count(*) FILTER (WHERE observed IS NULL) AS "missingTimeRows",
               count(DISTINCT event_key) FILTER (WHERE event_conflict) AS "conflictingEventKeys",
               count(DISTINCT case_key) FILTER (WHERE observed IS NULL) AS "casesWithUnplacedEvent",
               (SELECT count(*) FROM ordered_events WHERE NOT reliable) AS "ambiguousOrderRows",
               (SELECT count(*) FROM pairs) AS "candidatePairs",
               (SELECT count(*) FROM pairs WHERE excluded_reason IS NULL) AS "includedPairs",
               strftime(make_timestamp(epoch_us(min(observed))), '%Y-%m-%dT%H:%M:%S.%fZ')
                   AS "firstObservationUtc",
               strftime(make_timestamp(epoch_us(max(observed))), '%Y-%m-%dT%H:%M:%S.%fZ')
                   AS "lastObservationUtc"
        FROM events
    """, [input_rows, input_rows])[0]
    quality["excludedPairs"] = {
        reason: count for reason, count in db.execute("""
            SELECT excluded_reason, count(*) FROM pairs
            WHERE excluded_reason IS NOT NULL GROUP BY excluded_reason ORDER BY excluded_reason
        """).fetchall()
    }
    quality["longGapSeconds"] = long_gap_seconds
    db.execute("""
        CREATE TEMP TABLE variants AS
        WITH observable_cases AS (
            SELECT list(reader_key ORDER BY observed, sequence_no) AS trace
            FROM ordered_events GROUP BY case_key
            HAVING bool_and(reliable AND NOT event_conflict AND NOT has_unplaced_event AND reader_key IS NOT NULL)
        )
        SELECT trace, count(*) AS "caseCount" FROM observable_cases GROUP BY trace
    """)
    variant_summary = records(db, """
        SELECT count(*) AS "distinctVariantCount", coalesce(sum("caseCount"), 0) AS "observableCaseCount"
        FROM variants
    """)[0]
    variant_summary["topVariants"] = records(
        db, """
            SELECT list_transform(trace, reader_key -> sha256(reader_key)) AS "nodeIds", "caseCount"
            FROM variants ORDER BY "caseCount" DESC, trace LIMIT 20
        """,
    )
    return {
        "schemaVersion": "1.0", "mappingStatus": mapping.status,
        "semantics": "observed_directly_follows",
        "nodes": nodes, "edges": edges, "quality": quality, "variants": variant_summary,
    }


def discover(
    inputs: list[Path], mapping: Mapping, *, allow_candidate: bool = False,
    long_gap_seconds: float = 86_400,
) -> dict[str, Any]:
    validate_mapping(mapping, allow_candidate, long_gap_seconds)
    try:
        paths = parquet_paths(inputs)
        versions = file_versions(paths)
        with local_database() as db:
            input_rows = load_events(db, paths, mapping)
            graph = graph_data(db, mapping, input_rows, long_gap_seconds)
        hashes = []
        for path in paths:
            with path.open("rb") as file:
                hashes.append(file_digest(file, "sha256").hexdigest())
        if file_versions(parquet_paths(inputs)) != versions:
            raise DiscoveryError("Input files changed during discovery. Retry with a stable snapshot.")
    except (OSError, duckdb.Error):
        raise DiscoveryError("Unable to process the local Parquet snapshot.") from None
    except ProfileError as error:
        raise DiscoveryError(str(error)) from None

    graph["source"] = {
        "fileCount": len(paths), "inputFingerprint": digest(sorted(hashes)),
        "mappingFingerprint": digest(asdict(mapping)), "repeatedContentFiles": len(hashes) - len(set(hashes)),
    }
    graph["topologyId"] = digest(graph)
    return graph
