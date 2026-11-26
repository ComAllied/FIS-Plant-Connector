"""Read the versioned source-to-event mapping used by profiling."""

from dataclasses import dataclass
from pathlib import Path

import yaml


REQUIRED_FIELDS = ("case_id", "reader_id", "event_time")
OPTIONAL_FIELDS = (
    "event_id", "sequence_id", "plant_id", "line_id", "area_id",
    "reader_name", "description",
)
TIMESTAMP_TYPES = {
    "TIMESTAMP", "TIMESTAMP_S", "TIMESTAMP_MS", "TIMESTAMP_NS",
    "TIMESTAMP WITH TIME ZONE",
}


class MappingError(ValueError):
    """Mapping is missing, malformed, or unsupported."""


class MappingLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise MappingError("Duplicate key in the YAML mapping.")
        return mapping


@dataclass(frozen=True)
class Field:
    columns: tuple[str, ...]
    types: tuple[str, ...]


@dataclass(frozen=True)
class Mapping:
    status: str
    fields: dict[str, Field]


def load_mapping(path: Path) -> Mapping:
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=MappingLoader)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise MappingError("Unable to read the YAML mapping.") from None

    if not isinstance(document, dict) or set(document) != {"schema_version", "status", "fields"}:
        raise MappingError("Mapping requires schema_version, status and fields.")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise MappingError("Unsupported mapping schema version.")
    status = document["status"]
    if status not in ("candidate", "confirmed", "synthetic"):
        raise MappingError("Mapping status must be candidate, confirmed or synthetic.")

    fields = document["fields"]
    if not isinstance(fields, dict) or not set(REQUIRED_FIELDS).issubset(fields):
        raise MappingError("Mapping requires case_id, reader_id and event_time.")
    if set(fields).difference(REQUIRED_FIELDS, OPTIONAL_FIELDS):
        raise MappingError("Mapping contains an unknown event field.")

    parsed = {}
    for name, spec in fields.items():
        if not isinstance(spec, dict) or set(spec) != {"columns", "types"}:
            raise MappingError(f"{name} requires columns and types.")
        columns, types = spec["columns"], spec["types"]
        if not all(
            isinstance(items, list) and items and
            all(isinstance(item, str) and item.strip() and "\0" not in item for item in items)
            for items in (columns, types)
        ):
            raise MappingError(f"{name} requires nonempty lists of source columns and types.")
        if len(columns) != len(types) or len(set(columns)) != len(columns):
            raise MappingError(f"{name} requires one type per distinct source column.")
        parsed[name] = Field(tuple(columns), tuple(kind.strip().upper() for kind in types))

    time = parsed["event_time"]
    if len(time.columns) != 1 or time.types[0] not in TIMESTAMP_TYPES:
        raise MappingError("event_time must map to one native timestamp column for profiling.")
    return Mapping(status, parsed)
