"""Write a two-day synthetic event log for local smoke tests."""

from pathlib import Path

import duckdb


def write_demo(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    days = (
        (directory / "synthetic-day-1.parquet", (
            ("P", "001", "L1", "A", "2026-01-01 23:58:00+00", "E1", 1),
            ("P", "002", "L2", "A", "2026-01-01 23:59:00+00", "E2", 1),
            ("P", "003", "L1", "D", "2026-01-01 23:58:00+00", "E3", 1),
        )),
        (directory / "synthetic-day-2.parquet", (
            ("P", "001", "L1", "B", "2026-01-02 00:04:00+00", "E4", 2),
            ("P", "001", "L1", "B", "2026-01-02 00:04:00+00", "E4", 2),
            ("P", "001", "L1", "A", "2026-01-02 00:06:00+00", "E5", 3),
            ("P", "002", "L2", "B", "2026-01-02 00:07:00+00", "E6", None),
            ("P", "002", "L2", "C", "2026-01-02 00:07:00+00", "E7", None),
            ("P", "004", None, "A", "2026-01-02 00:08:00+00", "E8", 1),
        )),
    )
    if any(path.exists() or path.is_symlink() for path, _ in days):
        raise FileExistsError("A synthetic demo file already exists.")
    with duckdb.connect(config={
        "autoinstall_known_extensions": "false",
        "autoload_known_extensions": "false",
    }) as db:
        db.execute("""
            CREATE TABLE events (
                site VARCHAR, vehicle VARCHAR, lane VARCHAR, reader VARCHAR,
                observed_at TIMESTAMPTZ, event_key VARCHAR, ordering BIGINT
            )
        """)
        for path, rows in days:
            db.execute("DELETE FROM events")
            db.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
            db.execute("COPY events TO ? (FORMAT PARQUET)", [str(path.resolve())])
