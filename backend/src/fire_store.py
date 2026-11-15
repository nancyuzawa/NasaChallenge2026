"""SQLite indexado, com checkpoints persistentes de ingestão."""

import math
import sqlite3
from pathlib import Path

RADIUS = 6371007.181
COS30 = math.cos(math.radians(30))

SCHEMA = """
CREATE TABLE IF NOT EXISTS detections (
    sensor TEXT NOT NULL,
    satellite TEXT NOT NULL,
    acq_date TEXT NOT NULL,
    acq_time TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    confidence TEXT,
    frp REAL,
    cell_x INTEGER NOT NULL,
    cell_y INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    PRIMARY KEY (
        sensor, satellite, acq_date, acq_time,
        latitude, longitude, source_file
    )
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS detections_date
ON detections(acq_date, latitude, longitude);

CREATE INDEX IF NOT EXISTS detections_location
ON detections(latitude, longitude, acq_date);

CREATE TABLE IF NOT EXISTS sources (
    path TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    rows_read INTEGER,
    rows_valid INTEGER,
    rows_invalid INTEGER
);

CREATE TABLE IF NOT EXISTS ingestion_progress (
    source_key TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    next_chunk INTEGER NOT NULL DEFAULT 0,
    complete INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily (
    acq_date TEXT,
    sensor TEXT,
    cell_x INTEGER,
    cell_y INTEGER,
    latitude REAL,
    longitude REAL,
    detections INTEGER,
    PRIMARY KEY(acq_date, sensor, cell_x, cell_y)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS daily_location
ON daily(latitude, longitude, acq_date);
"""

INSERT = """
INSERT OR IGNORE INTO detections
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def grid(latitude, longitude):
    return (
        math.floor(
            RADIUS * math.radians(longitude) * COS30 / 1000
        ),
        math.floor(
            RADIUS * math.sin(math.radians(latitude)) / COS30 / 1000
        ),
    )


def connect(path):
    path = str(path)

    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA foreign_keys=ON")

    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

    conn.executescript(SCHEMA)
    return conn


def insert_frame(conn, frame, table="detections"):
    rows = []

    for row in frame.itertuples(index=False):
        x, y = grid(row.latitude, row.longitude)

        rows.append((
            row.sensor,
            row.satellite or "",
            row.acq_date,
            row.acq_time,
            row.latitude,
            row.longitude,
            row.confidence,
            row.frp,
            x,
            y,
            row.source_file,
        ))

    if table not in ("detections", "ingestion_staging"):
        raise ValueError("Tabela de ingestao invalida.")
    conn.executemany(INSERT.replace("INTO detections", f"INTO {table}"), rows)


def refresh_daily(conn):
    conn.execute("DELETE FROM daily")

    conn.execute("""
        INSERT INTO daily
        SELECT
            acq_date,
            sensor,
            cell_x,
            cell_y,
            AVG(latitude),
            AVG(longitude),
            COUNT(*)
        FROM (
            SELECT DISTINCT
                sensor, satellite, acq_date, acq_time,
                latitude, longitude, cell_x, cell_y
            FROM detections
        )
        GROUP BY acq_date, sensor, cell_x, cell_y
    """)

    conn.commit()


def readonly(path, timeout=60):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=timeout)