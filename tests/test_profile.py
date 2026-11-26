import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from fis_twin.demo import write_demo
from fis_twin.mapping import MappingError, load_mapping
from fis_twin.profile import ProfileError, profile_parquet


EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "mapping.example.yaml"


def write_parquet(path: Path, query: str) -> Path:
    with duckdb.connect() as db:
        db.execute(f"COPY ({query}) TO ? (FORMAT PARQUET)", [str(path)])
    return path


def test_demo_profiles_multiple_files_and_keeps_ties(tmp_path: Path) -> None:
    write_demo(tmp_path)
    mapping = load_mapping(EXAMPLE)
    files = sorted(tmp_path.glob("*.parquet"))
    report = profile_parquet([tmp_path, files[1], files[0]], mapping)

    assert report == profile_parquet(list(reversed(files)), mapping)
    assert report["fileCount"] == 2
    assert report["totalRows"] == 9
    assert report["schemaDrift"] == []
    storage = report["parquetStorageSchemas"]
    assert len(storage) == 1 and storage[0]["fileIndexes"] == [1, 2]
    timestamp = next(field for field in storage[0]["fields"] if field["name"] == "observed_at")
    assert timestamp["physicalType"] == "INT64"
    assert "isAdjustedToUTC=1" in timestamp["logicalType"]
    assert [file["rowCount"] for file in report["files"]] == [3, 6]
    assert report["mapping"]["schemaCompatible"] is True
    quality = report["mapping"]["quality"]
    assert quality["invalidRequiredRows"] == 1
    assert quality["distinctCaseKeys"] == 4
    assert quality["distinctReaderKeys"] == 6
    assert quality["tiedCaseTimeGroups"] == 2
    assert quality["rowsInTiedCaseTimeGroups"] == 4
    assert quality["tiedGroupsWithMultipleReaders"] == 1
    assert quality["tiedGroupsWithCompleteUniqueSequence"] == 0
    assert quality["repeatedEventKeys"] == 1
    assert quality["excessRowsWithRepeatedEventKeys"] == 1


def test_schema_drift_is_reported_without_coercion(tmp_path: Path) -> None:
    write_demo(tmp_path)
    write_parquet(
        tmp_path / "other.parquet",
        "SELECT 1::BIGINT AS vehicle, 'additional' AS extra, 'P' AS site",
    )
    report = profile_parquet([tmp_path], load_mapping(EXAMPLE))

    assert report["totalRows"] == 10
    drift = {item["column"]: item for item in report["schemaDrift"]}
    assert drift["vehicle"]["types"] == ["BIGINT", "VARCHAR"]
    assert drift["extra"]["missingFromFiles"] == [2, 3]
    assert len(report["parquetStorageSchemas"]) == 2
    assert report["mapping"]["schemaCompatible"] is False
    assert report["mapping"]["quality"] is None
    issues = {issue["code"] for issue in report["files"][0]["mappingIssues"]}
    assert issues == {"missing_column", "type_mismatch"}


def test_unmapped_type_drift_does_not_invalidate_mapping(tmp_path: Path) -> None:
    write_demo(tmp_path)
    files = sorted(tmp_path.glob("*.parquet"))
    first = tmp_path / "new-1.parquet"
    second = tmp_path / "new-2.parquet"
    with duckdb.connect() as db:
        for path, source, extra in zip((first, second), files, ("1", "[1, 2]"), strict=True):
            db.execute(
                f"COPY (SELECT *, {extra} AS ignored FROM read_parquet($source)) "
                "TO $target (FORMAT PARQUET)",
                {"source": str(source), "target": str(path)},
            )

    report = profile_parquet([first, second], load_mapping(EXAMPLE))
    assert report["schemaDrift"][0]["column"] == "ignored"
    assert report["mapping"]["schemaCompatible"] is True
    assert report["mapping"]["quality"]["invalidRequiredRows"] == 1


def test_empty_inputs_and_zero_row_file(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="contains no Parquet files"):
        profile_parquet([tmp_path])
    path = write_parquet(tmp_path / "empty.parquet", "SELECT ''::VARCHAR AS text WHERE false")
    report = profile_parquet([path])
    assert report["totalRows"] == 0
    assert report["files"][0]["columns"] == [
        {"name": "text", "type": "VARCHAR", "nullCount": 0, "blankCount": 0},
    ]


def test_zero_rows_with_compatible_mapping(tmp_path: Path) -> None:
    write_demo(tmp_path)
    source = tmp_path / "synthetic-day-1.parquet"
    path = tmp_path / "empty.parquet"
    with duckdb.connect() as db:
        db.execute(
            "COPY (SELECT * FROM read_parquet($source) LIMIT 0) TO $target (FORMAT PARQUET)",
            {"source": str(source), "target": str(path)},
        )

    quality = profile_parquet([path], load_mapping(EXAMPLE))["mapping"]["quality"]
    assert quality["eventTimeRange"] == {"min": None, "max": None}
    assert quality["tiedCaseTimeGroups"] == 0
    assert quality["invalidRequiredRows"] == 0
    assert quality["repeatedEventKeys"] == 0


def test_cli_reports_counts_and_never_emits_example_values(tmp_path: Path) -> None:
    path = write_parquet(
        tmp_path / "private-example.parquet",
        '''SELECT value AS "name""with quote" FROM (VALUES
          (NULL::VARCHAR), (chr(9)), (' '), ('unique-sensitive-test-value')
        ) AS samples(value)''',
    )
    output = tmp_path / "report.json"
    run = subprocess.run(
        [sys.executable, "-m", "fis_twin.cli", "profile", "--input", str(path), "--output", str(output)],
        capture_output=True, text=True, check=True,
    )
    report_text = output.read_text(encoding="utf-8")
    assert "unique-sensitive-test-value" not in run.stdout + run.stderr + report_text
    assert path.name not in report_text
    columns = json.loads(report_text)["files"][0]["columns"]
    assert columns == [{"name": 'name"with quote', "type": "VARCHAR", "nullCount": 1, "blankCount": 2}]


def test_corrupt_input_leaves_existing_report_untouched(tmp_path: Path) -> None:
    path = tmp_path / "confidential-file-name.parquet"
    path.write_text("invalid parquet", encoding="utf-8")
    output = tmp_path / "report.json"
    output.write_text("previous report", encoding="utf-8")
    run = subprocess.run(
        [sys.executable, "-m", "fis_twin.cli", "profile", "--input", str(path), "--output", str(output)],
        capture_output=True, text=True, check=False,
    )
    assert run.returncode == 1
    assert "Unable to read Parquet input file 1" in run.stderr
    assert path.name not in run.stderr
    assert output.read_text(encoding="utf-8") == "previous report"


def test_duplicate_mapping_key_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "invalid.yaml"
    config.write_text(EXAMPLE.read_text(encoding="utf-8") + "status: confirmed\n", encoding="utf-8")
    with pytest.raises(MappingError, match="Duplicate key"):
        load_mapping(config)
