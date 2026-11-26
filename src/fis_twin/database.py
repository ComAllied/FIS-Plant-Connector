"""Isolated DuckDB connections for local Parquet processing."""

from collections.abc import Iterator
from contextlib import contextmanager
from tempfile import TemporaryDirectory

import duckdb


@contextmanager
def local_database() -> Iterator[duckdb.DuckDBPyConnection]:
    with TemporaryDirectory(prefix="fis-twin-duckdb-") as temporary:
        with duckdb.connect(config={
            "temp_directory": temporary,
            "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false",
        }) as connection:
            yield connection
