import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "dailyanchor.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS routines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL REFERENCES routines(id),
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    expected_time TEXT NOT NULL,
    window_minutes INTEGER NOT NULL DEFAULT 60
);

CREATE TABLE IF NOT EXISTS completions (
    id TEXT PRIMARY KEY,
    step_id TEXT NOT NULL REFERENCES steps(id),
    routine_id TEXT NOT NULL REFERENCES routines(id),
    completed_at TEXT NOT NULL,
    log_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS step_overrides (
    step_id TEXT NOT NULL,
    log_date TEXT NOT NULL,
    expected_time TEXT NOT NULL,
    PRIMARY KEY (step_id, log_date)
);
"""


def get_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    if db_path == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        path = Path(db_path) if db_path else DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
