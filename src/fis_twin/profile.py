"""Produce a local, aggregate-only report for Parquet inputs."""

from pathlib import Path
from typing import Any

import duckdb

from .database import local_database
from .mapping import Field, Mapping, REQUIRED_FIELDS, TIMESTAMP_TYPES


class ProfileError(ValueError):
    """Profiling cannot safely produce a complete report."""


def parquet_paths(inputs: list[Path]) -> list[Path]:
    paths: set[Path] = set()
    for index, path in enumerate(inputs, start=1):
        if path.is_dir():
            files = {
                item.resolve() for item in path.rglob("*")
                if item.suffix.lower() == ".parquet" and item.is_file()
            }
            if not files:
                raise ProfileError(f"Input {index} directory contains no Parquet files.")
            paths.update(files)
        elif path.is_file() and path.suffix.lower() == ".parquet":
            paths.add(path.resolve())
        else:
            raise ProfileError(f"Input {index} is not a directory or readable Parquet file.")
    if not paths:
        raise ProfileError("Provide at least one Parquet input.")
    return sorted(paths)


def identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def blank(column: str) -> str:
    return rf"regexp_full_match({column}, '\s*')"


def invalid(field: Field) -> str:
    conditions = []
    for name, kind in zip(field.columns, field.types, strict=True):
        column = identifier(name)
        conditions.append(f"{column} IS NULL")
        if kind == "VARCHAR":
            conditions.append(blank(column))
        elif kind in TIMESTAMP_TYPES:
            conditions.append(f"NOT isfinite({column})")
    return f"({' OR '.join(conditions)})"


def key(field: Field) -> str:
    columns = [identifier(name) for name in field.columns]
    if len(columns) == 1:
        return columns[0]
    return f"row({', '.join(columns)})"


def parquet_storage_schema(db: duckdb.DuckDBPyConnection, path: Path) -> tuple[tuple, ...]:
    return tuple(db.execute(
        """
        SELECT name, type, repetition_type, num_children, logical_type, converted_type,
               type_length, scale, precision, field_id
        FROM parquet_schema(?)
        """,
        [str(path)],
    ).fetchall())


def parquet_columns(db: duckdb.DuckDBPyConnection, path: Path) -> dict[str, str]:
    return {
        name: kind for name, kind, *_ in db.execute(
            "DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=false)", [str(path)]
        ).fetchall()
    }


def mapping_issues(schema: dict[str, str], mapping: Mapping) -> list[dict[str, Any]]:
    issues = []
    for field, spec in mapping.fields.items():
        for name, kind in zip(spec.columns, spec.types, strict=True):
            actual = schema.get(name)
            if actual != kind:
                issues.append({
                    "field": field, "column": name, "expectedType": kind, "actualType": actual,
                    "code": "missing_column" if actual is None else "type_mismatch",
                })
    return issues


def profile_file(
    db: duckdb.DuckDBPyConnection, path: Path, index: int, mapping: Mapping | None
) -> dict[str, Any]:
    source = "read_parquet(?, hive_partitioning=false)"
    schema = parquet_columns(db, path)
    expressions = ["count(*)"]
    for name, kind in schema.items():
        column = identifier(name)
        expressions.append(f"count(*) FILTER (WHERE {column} IS NULL)")
        if kind == "VARCHAR":
            expressions.append(f"count(*) FILTER (WHERE {blank(column)})")
    rows, *counts = db.execute(
        f"SELECT {', '.join(expressions)} FROM {source}", [str(path)]
    ).fetchall()[0]
    counts = iter(counts)
    columns = []
    for name, kind in schema.items():
        entry = {"name": name, "type": kind, "nullCount": next(counts)}
        if kind == "VARCHAR":
            entry["blankCount"] = next(counts)
        columns.append(entry)

    result = {"fileIndex": index, "rowCount": rows, "columns": columns}
    if mapping:
        result["mappingIssues"] = mapping_issues(schema, mapping)
    return result


def schema_drift(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    locations: dict[str, dict[int, str]] = {}
    for file in files:
        for column in file["columns"]:
            locations.setdefault(column["name"], {})[file["fileIndex"]] = column["type"]
    file_indexes = {file["fileIndex"] for file in files}
    drift = []
    for name, indexes in sorted(locations.items()):
        types = sorted(set(indexes.values()))
        missing = sorted(file_indexes - indexes.keys())
        if missing or len(types) > 1:
            drift.append({"column": name, "types": types, "missingFromFiles": missing})
    return drift


def mapped_quality(
    db: duckdb.DuckDBPyConnection, paths: list[Path], mapping: Mapping
) -> dict[str, Any]:
    fields = mapping.fields
    columns = dict.fromkeys(column for field in fields.values() for column in field.columns)
    projection = ", ".join(map(identifier, columns))
    # Project before combining files, so unmapped schema drift cannot trigger casts.
    sources = " UNION ALL ".join(
        f"SELECT {projection} FROM read_parquet(?, hive_partitioning=false)" for _ in paths
    )
    parameters = [str(path) for path in paths]
    invalid_fields = {name: invalid(field) for name, field in fields.items()}
    invalid_required = " OR ".join(invalid_fields[name] for name in REQUIRED_FIELDS)
    quality_counts = ", ".join(
        f"count(*) FILTER (WHERE {condition})" for condition in invalid_fields.values()
    )
    case, reader, event_time = (key(fields[name]) for name in REQUIRED_FIELDS)
    bad_case, bad_reader, bad_time = (invalid_fields[name] for name in REQUIRED_FIELDS)
    invalid_count, case_count, reader_count, first_time, last_time, *field_counts = db.execute(
        f"""
        WITH events AS ({sources})
        SELECT count(*) FILTER (WHERE {invalid_required}),
               count(DISTINCT {case}) FILTER (WHERE NOT {bad_case}),
               count(DISTINCT {reader}) FILTER (WHERE NOT {bad_reader}),
               cast(min({event_time}) FILTER (WHERE NOT {bad_time}) AS VARCHAR),
               cast(max({event_time}) FILTER (WHERE NOT {bad_time}) AS VARCHAR),
               {quality_counts}
        FROM events
        """,
        parameters,
    ).fetchall()[0]

    usable_sequence = "FALSE"
    if "sequence_id" in fields:
        sequence = key(fields["sequence_id"])
        usable_sequence = (
            f"count(DISTINCT {sequence}) FILTER (WHERE NOT {invalid_fields['sequence_id']})"
            " = count(*)"
        )
    tied_groups, tied_rows, tied_groups_multiple_readers, sequence_groups = db.execute(
        f"""
        WITH events AS ({sources}), ties AS (
            SELECT count(*) AS events_in_group,
                   count(DISTINCT {reader}) FILTER (WHERE NOT {bad_reader}) AS reader_count,
                   {usable_sequence} AS complete_unique_sequence
            FROM events
            WHERE NOT {bad_case} AND NOT {bad_time}
            GROUP BY {case}, {event_time}
            HAVING count(*) > 1
        )
        SELECT count(*), coalesce(sum(events_in_group), 0),
               count(*) FILTER (WHERE reader_count > 1),
               count(*) FILTER (WHERE complete_unique_sequence)
        FROM ties
        """,
        parameters,
    ).fetchall()[0]
    result = {
        "invalidRequiredRows": invalid_count,
        "invalidRowsByField": dict(zip(fields, field_counts, strict=True)),
        "distinctCaseKeys": case_count,
        "distinctReaderKeys": reader_count,
        "eventTimeRange": {"min": first_time, "max": last_time},
        "tiedCaseTimeGroups": tied_groups,
        "rowsInTiedCaseTimeGroups": tied_rows,
        "tiedGroupsWithMultipleReaders": tied_groups_multiple_readers,
        "tiedGroupsWithCompleteUniqueSequence": sequence_groups if "sequence_id" in fields else None,
    }
    if "event_id" in fields:
        event_id = key(fields["event_id"])
        repeated_keys, excess_rows = db.execute(
            f"""
            WITH events AS ({sources}), repeated AS (
                SELECT count(*) AS occurrences
                FROM events
                WHERE NOT {invalid_fields['event_id']}
                GROUP BY {event_id}
                HAVING count(*) > 1
            )
            SELECT count(*), coalesce(sum(occurrences - 1), 0) FROM repeated
            """,
            parameters,
        ).fetchall()[0]
        result["repeatedEventKeys"] = repeated_keys
        result["excessRowsWithRepeatedEventKeys"] = excess_rows
    return result


def profile_parquet(inputs: list[Path], mapping: Mapping | None = None) -> dict[str, Any]:
    paths = parquet_paths(inputs)
    with local_database() as db:
        files = []
        storage_schemas: dict[tuple[tuple, ...], list[int]] = {}
        for index, path in enumerate(paths, start=1):
            try:
                storage_schema = parquet_storage_schema(db, path)
                storage_schemas.setdefault(storage_schema, []).append(index)
                files.append(profile_file(db, path, index, mapping))
            except duckdb.Error:
                raise ProfileError(f"Unable to read Parquet input file {index}.") from None
        metadata_fields = (
            "name", "physicalType", "repetitionType", "childCount", "logicalType", "convertedType",
            "typeLength", "scale", "precision", "fieldId",
        )
        report = {
            "profileVersion": 1,
            "fileCount": len(files),
            "totalRows": sum(file["rowCount"] for file in files),
            "schemaDrift": schema_drift(files),
            "parquetStorageSchemas": [
                {
                    "fileIndexes": indexes,
                    "fields": [dict(zip(metadata_fields, field, strict=True)) for field in schema],
                }
                for schema, indexes in storage_schemas.items()
            ],
            "files": files,
        }
        if mapping:
            compatible = not any(file["mappingIssues"] for file in files)
            try:
                quality = mapped_quality(db, paths, mapping) if compatible else None
            except duckdb.Error:
                raise ProfileError("Unable to compute aggregate mapping quality.") from None
            report["mapping"] = {
                "status": mapping.status, "schemaCompatible": compatible, "quality": quality,
            }
    return report
