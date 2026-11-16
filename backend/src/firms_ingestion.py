
"""Ingestão FIRMS incremental com checkpoints e Parquet."""

from pathlib import Path
from zipfile import ZipFile
from fnmatch import fnmatch
import json
import re

import pandas as pd

from .fire_store import connect, insert_frame
from .parquet_writer import LAYOUT_VERSION, export_source

DEFAULT_CHUNK_SIZE = 50_000

OUTPUT_COLUMNS = [
    "sensor", "satellite", "acq_date", "acq_time",
    "latitude", "longitude", "confidence", "frp",
    "source_file",
]

ALIASES = {
    "lat": "latitude",
    "lon": "longitude",
    "long": "longitude",
    "date": "acq_date",
    "time": "acq_time",
    "sat": "satellite",
    "conf": "confidence",
}


def prepare_dataframe(frame, sensor, source_file, start_year=2020, end_year=2025):
    if sensor.upper() not in ("MODIS", "VIIRS"):
        raise ValueError("Sensor inválido.")

    df = frame.copy()

    df.columns = [
        ALIASES.get(str(c).strip().lower(), str(c).strip().lower())
        for c in df.columns
    ]

    df = df.loc[:, ~df.columns.duplicated()].copy()

    required = {"latitude", "longitude", "acq_date", "acq_time"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{source_file}: colunas ausentes: {sorted(missing)}"
        )

    for col in ("latitude", "longitude"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    dates = pd.to_datetime(df["acq_date"], errors="coerce")
    df["acq_date"] = dates.dt.strftime("%Y-%m-%d")

    times = (
        df["acq_time"]
        .astype("string")
        .str.strip()
        .str.replace(":", "", regex=False)
        .str.replace(r"\.0$", "", regex=True)
    )

    times = times.where(times.str.fullmatch(r"\d{1,4}")).str.zfill(4)

    hours = pd.to_numeric(times.str[:2], errors="coerce")
    minutes = pd.to_numeric(times.str[2:], errors="coerce")

    df["acq_time"] = times
    df["sensor"] = sensor.upper()

    for col in ("satellite", "confidence"):
        if col not in df:
            df[col] = ""

        df[col] = df[col].fillna("").astype(str).str.strip()

    df["frp"] = pd.to_numeric(
        df.get("frp", pd.Series(index=df.index, dtype=float)),
        errors="coerce",
    )

    df["source_file"] = source_file

    valid = (
        df.latitude.between(-90, 90)
        & df.longitude.between(-180, 180)
        & dates.notna()
        & hours.between(0, 23)
        & minutes.between(0, 59)
    )

    in_period = (
        dates.dt.year.between(start_year, end_year)
    )

    selected = valid & in_period

    report = {
        "source_file": source_file,
        "sensor": sensor.upper(),
        "rows_read": len(df),
        "rows_valid": int(selected.sum()),
        "rows_invalid": int((~valid).sum()),
        "rows_outside_period": int((valid & ~in_period).sum()),
    }

    result = df.loc[selected, OUTPUT_COLUMNS].copy()

    result["frp"] = (
        result["frp"]
        .astype(object)
        .where(result["frp"].notna(), None)
    )

    return result, report


def discover_sensor_files(folder):
    return sorted(
        p for p in Path(folder).rglob("*")
        if p.is_file()
        and (
            p.suffix.lower() in (".csv", ".zip")
            or p.name.lower().endswith(".csv.gz")
        )
    )


def candidate_years(path):
    """Detecta anos no nome e nos diretórios do arquivo."""

    text = str(path)
    return {
        int(year)
        for year in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text)
    }


def iter_csv_files(path, chunk_size):
    if path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.lower().endswith(".csv"):
                    continue

                with archive.open(member) as stream:
                    reader = pd.read_csv(
                        stream,
                        encoding="utf-8-sig",
                        chunksize=chunk_size,
                    )

                    try:
                        yield member, reader
                        # O consumo acontece no chamador.
                    finally:
                        reader.close()
    else:
        reader = pd.read_csv(
            path,
            encoding="utf-8-sig",
            chunksize=chunk_size,
        )

        try:
            yield path.name, reader
        finally:
            reader.close()


def fingerprint(path):
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"

def _source_condition(column):
    return f"({column} = ? OR substr({column}, 1, ?) = ?)"


def _source_params(source):
    prefix = source + "::"
    return source, len(prefix), prefix


def _initialize_checkpoints(conn):
    # Persist staging across interruptions; readers keep the previous version.
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'detections'"
    ).fetchone()[0]
    conn.execute(schema.replace(
        "CREATE TABLE detections", "CREATE TABLE IF NOT EXISTS ingestion_staging", 1
    ))
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS staging_source
        ON ingestion_staging(source_file, acq_date);
        CREATE INDEX IF NOT EXISTS detections_source
        ON detections(source_file, acq_date);
        CREATE TABLE IF NOT EXISTS ingestion_years (
            source TEXT NOT NULL,
            year INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            chunk_size INTEGER NOT NULL,
            next_chunk INTEGER NOT NULL DEFAULT 0,
            complete INTEGER NOT NULL DEFAULT 0,
            exported INTEGER NOT NULL DEFAULT 0,
            report TEXT NOT NULL,
            export_keys TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY(source, year)
        );
    """)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(ingestion_years)")}
    if "layout_version" not in columns:
        with conn:
            conn.execute("ALTER TABLE ingestion_years ADD COLUMN layout_version INTEGER NOT NULL DEFAULT 0")


def _ingest_source_year(conn, path, source, sensor, year, output_dir, chunk_size):
    signature = fingerprint(path)
    checkpoint = conn.execute(
        """SELECT fingerprint, chunk_size, next_chunk, complete, exported,
                  report, export_keys, layout_version FROM ingestion_years
           WHERE source = ? AND year = ?""", (source, year),
    ).fetchone()
    period = (f"{year}-01-01", f"{year + 1}-01-01")
    condition = _source_condition("source_file") + " AND acq_date >= ? AND acq_date < ?"
    params = (*_source_params(source), *period)
    reusable = checkpoint and checkpoint[0] == signature
    if reusable and checkpoint[3] and checkpoint[4] and checkpoint[7] == LAYOUT_VERSION:
        print(f"[cache] {year} {source}", flush=True)
        return None
    if reusable and not checkpoint[3] and checkpoint[1] != chunk_size:
        # Chunk offsets only make sense with the original chunk size.
        reusable = False
    if reusable:
        next_chunk = checkpoint[2]
        complete = checkpoint[3]
        report = json.loads(checkpoint[5])
        export_keys = json.loads(checkpoint[6])
    else:
        next_chunk, complete, export_keys = 0, False, []
        report = dict(source_file=source, sensor=sensor.upper(), year=year,
                      rows_read=0, rows_valid=0, rows_invalid=0, rows_outside_period=0)
        with conn:
            conn.execute(f"DELETE FROM ingestion_staging WHERE {condition}", params)
            conn.execute(
                """INSERT OR REPLACE INTO ingestion_years
                   (source, year, fingerprint, chunk_size, report)
                   VALUES (?, ?, ?, ?, ?)""",
                (source, year, signature, chunk_size, json.dumps(report)),
            )
    if not complete:
        print(f"[processando] {year} {source} | checkpoint {next_chunk}", flush=True)
        chunk_index = 0
        for member, chunks in iter_csv_files(path, chunk_size):
            source_key = source + "::" + member if path.suffix.lower() == ".zip" else source
            for chunk in chunks:
                chunk_index += 1
                if chunk_index <= next_chunk:
                    continue
                normalized, stats = prepare_dataframe(chunk, sensor, source_key, year, year)
                for key in ("rows_read", "rows_valid", "rows_invalid", "rows_outside_period"):
                    report[key] += stats[key]
                with conn:
                    insert_frame(conn, normalized, table="ingestion_staging")
                    conn.execute(
                        """UPDATE ingestion_years SET next_chunk = ?, report = ?
                           WHERE source = ? AND year = ?""",
                        (chunk_index, json.dumps(report), source, year),
                    )
                print(f"[chunk] {year} {source_key} | {chunk_index} | "
                      f"{stats['rows_valid']:,} validas", flush=True)
        if fingerprint(path) != signature:
            raise RuntimeError(f"Arquivo alterado durante a leitura: {path}. Execute novamente.")
        # Replace only this source/year, in one transaction, after validation.
        with conn:
            export_keys = [row[0] for row in conn.execute(
                f"SELECT DISTINCT source_file FROM detections WHERE {condition} "
                f"UNION SELECT DISTINCT source_file FROM ingestion_staging WHERE {condition}",
                (*params, *params),
            )]
            conn.execute(f"DELETE FROM detections WHERE {condition}", params)
            conn.execute(
                f"INSERT OR IGNORE INTO detections SELECT * FROM ingestion_staging WHERE {condition}",
                params,
            )
            conn.execute(f"DELETE FROM ingestion_staging WHERE {condition}", params)
            conn.execute(
                """UPDATE ingestion_years SET complete = 1, export_keys = ?
                   WHERE source = ? AND year = ?""",
                (json.dumps(export_keys), source, year),
            )
    # Publication can be retried independently if interrupted after the DB commit.
    for source_key in export_keys:
        count = export_source(conn, output_dir, sensor, year, source_key)
        print(f"[CSV/Parquet] {year} {source_key}: {count:,} registros", flush=True)
    with conn:
        conn.execute(
            "UPDATE ingestion_years SET exported = 1, layout_version = ? WHERE source = ? AND year = ?",
            (LAYOUT_VERSION, source, year),
        )
        conn.execute(
            """INSERT OR REPLACE INTO sources
               (path, fingerprint, rows_read, rows_valid, rows_invalid)
               VALUES (?, ?, ?, ?, ?)""",
            (source, signature, report["rows_read"], report["rows_valid"], report["rows_invalid"]),
        )
    print(json.dumps(report, ensure_ascii=True), flush=True)
    return report


def ingest_all(raw_root, output_dir, chunk_size=DEFAULT_CHUNK_SIZE,
               start_year=2020, end_year=2025, match=None):
    """Process years in order, resuming each source from a committed chunk.

    Annual CSV/Parquet files are published per source. The frontend reads the
    SQLite database, where each source/year becomes visible atomically.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size precisa ser positivo.")
    if not 1900 <= start_year <= end_year <= 9998:
        raise ValueError("Periodo de anos invalido (1900 a 9998).")
    raw_root, output_dir = Path(raw_root), Path(output_dir)
    sources = []
    for sensor in ("modis", "viirs"):
        for path in discover_sensor_files(raw_root / sensor):
            if match and not fnmatch(path.name, match):
                continue
            # Only inspect paths within raw_root; the project name may contain a year.
            years = candidate_years(path.relative_to(raw_root))
            if years and not any(start_year <= year <= end_year for year in years):
                continue
            sources.append((sensor, path, years))
    if not sources:
        print("Nenhum arquivo encontrado para o periodo.")
        return []
    conn = connect(output_dir / "firewatch.sqlite")
    reports = []
    try:
        _initialize_checkpoints(conn)
        for year in range(start_year, end_year + 1):
            print(f"[ano] {year}", flush=True)
            for sensor, path, years in sources:
                if years and year not in years:
                    continue
                source = path.relative_to(raw_root).as_posix()
                report = _ingest_source_year(
                    conn, path, source, sensor, year, output_dir, chunk_size,
                )
                if report is not None:
                    reports.append(report)
        return reports
    finally:
        conn.close()
